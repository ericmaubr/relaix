"""Executor — two independent steps, deliberately decoupled (plan §2.3):

1. `evaluate_pending_events` matches each pending/error event against active
   rules for its source and creates one `webhook_rule_execution` row per
   match (an event is matched once; re-running this is a no-op for events
   already `done`).
2. `dispatch_pending_executions` sends the actual HTTP action call for each
   pending/error execution row — retryable independently of event matching,
   using the same atomic-claim pattern (plan §2.4)."""

from __future__ import annotations

import json

import requests

from relaix.matching import rule_matches
from relaix.repository import (
    EventRepository,
    RuleExecutionRepository,
    RuleRepository,
    SourceRepository,
)


def evaluate_pending_events(batch_size: int = 50) -> dict:
    events = EventRepository()
    rules_repo = RuleRepository()
    executions = RuleExecutionRepository()
    sources = SourceRepository()

    processed = 0
    matched = 0

    # Snapshot both statuses upfront — querying "error" after already having
    # processed "pending" in this same call would re-pick up an event that
    # just flipped to "error" moments ago, double-counting one attempt.
    candidates = events.list(status="pending", limit=batch_size) + events.list(
        status="error", limit=batch_size
    )

    for event in candidates:
        if event.status == "error":
            # malformed content never fixes itself — unlike a dispatch
            # failure, retrying forever just burns cycles, so this is
            # capped per-source (source.max_content_attempts).
            source = sources.get(event.source_id)
            max_attempts = source.max_content_attempts if source else 3
            if event.attempts >= max_attempts:
                continue
        if not events.claim(event.id):
            continue  # another worker already claimed it
        processed += 1

        try:
            payload = json.loads(event.raw_payload)
        except ValueError:
            events.finish(event.id, "error", event.attempts + 1)
            continue

        for rule in rules_repo.list(event.source_id):
            if not rule.active:
                continue
            conditions = rules_repo.list_conditions(rule.id)
            if not rule_matches(payload, conditions):
                continue
            if not executions.list(event_id=event.id, rule_id=rule.id):
                executions.create(event.id, rule.id)
            matched += 1

        events.finish(event.id, "done", event.attempts + 1)

    return {"events_processed": processed, "rules_matched": matched}


def dispatch_pending_executions(batch_size: int = 50) -> dict:
    executions = RuleExecutionRepository()
    rules_repo = RuleRepository()
    events = EventRepository()

    dispatched = 0
    succeeded = 0
    candidates = executions.list(status="pending", limit=batch_size) + executions.list(
        status="error", limit=batch_size
    )

    for execution in candidates:
        if not executions.claim(execution.id):
            continue  # another worker already claimed it
        dispatched += 1

        rule = rules_repo.get(execution.rule_id)
        event = events.get(execution.event_id)
        if rule is None or event is None:
            executions.finish(
                execution.id, "error", response_detail="rule or event no longer exists"
            )
            continue

        headers = {"Content-Type": "application/json"}
        if rule.action_token:
            headers["Authorization"] = f"Bearer {rule.action_token}"

        try:
            resp = requests.post(
                rule.action_url, data=event.raw_payload, headers=headers, timeout=30
            )
            status = "success" if resp.ok else "error"
            if status == "success":
                succeeded += 1
            executions.finish(
                execution.id,
                status,
                response_http_status=resp.status_code,
                response_detail=resp.text[:2000],
            )
        except requests.RequestException as e:
            executions.finish(execution.id, "error", response_detail=str(e))

    return {"dispatched": dispatched, "succeeded": succeeded}
