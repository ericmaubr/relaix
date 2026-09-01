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

from relaix.domain import WebhookSource
from relaix.email_parsing import build_email_envelope
from relaix.matching import rule_matches
from relaix.repository import (
    EventRepository,
    RuleExecutionRepository,
    RuleRepository,
    SourceRepository,
)


def _decode_payload(raw_payload: str, source: WebhookSource | None) -> dict:
    """Turns a stored `raw_payload` (the full webhook.site item — see
    collector.py) into the payload rules/dispatch actually operate on.

    - `type: "email"` → build the `{"email": {...}}` envelope (downloads
      attachments — see email_parsing.py).
    - `type: "web"` (or anything with a `content` key) → unchanged from
      before: `content` is the raw JSON body G-Click posted, so this keeps
      existing rules (`message.tarefa.nome`, ...) matching exactly as today.
    - Neither key present → the event was stored before this format existed
      (already-pending/error at deploy time) — treat it as the message
      itself, the old behavior."""
    item = json.loads(raw_payload)
    if item.get("type") == "email":
        return build_email_envelope(item, source)
    if "content" in item:
        return json.loads(item["content"])
    return item


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
        source = sources.get(event.source_id)
        if event.status == "error":
            # malformed content never fixes itself — unlike a dispatch
            # failure, retrying forever just burns cycles, so this is
            # capped per-source (source.max_content_attempts).
            max_attempts = source.max_content_attempts if source else 3
            if event.attempts >= max_attempts:
                continue
        if not events.claim(event.id):
            continue  # another worker already claimed it
        processed += 1

        try:
            payload = _decode_payload(event.raw_payload, source)
        except (ValueError, requests.RequestException):
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
    sources = SourceRepository()

    dispatched = 0
    succeeded = 0
    candidates = executions.list(status="pending", limit=batch_size) + executions.list(
        status="error", limit=batch_size
    )

    for execution in candidates:
        event = events.get(execution.event_id)
        if execution.status == "error":
            # A dispatch failure can be transient (target down briefly), so
            # unlike content parsing this used to retry unbounded — but
            # content that embeds a time-limited resource (e.g. a presigned
            # download URL) never becomes valid again either, so it still
            # needs a ceiling. Mirrors source.max_content_attempts.
            source = sources.get(event.source_id) if event else None
            max_attempts = source.max_dispatch_attempts if source else 3
            if execution.attempts >= max_attempts:
                executions.finish(
                    execution.id,
                    "abandoned",
                    response_detail="max dispatch attempts reached",
                    bump_attempts=False,
                )
                continue

        if not executions.claim(execution.id):
            continue  # another worker already claimed it
        dispatched += 1

        rule = rules_repo.get(execution.rule_id)
        if rule is None or event is None:
            executions.finish(
                execution.id, "error", response_detail="rule or event no longer exists"
            )
            continue

        headers = {"Content-Type": "application/json"}
        if rule.action_token:
            headers["Authorization"] = f"Bearer {rule.action_token}"

        try:
            # Re-decoded here (not reused from evaluate_pending_events) since
            # the payload isn't persisted — see executor.py's `_decode_payload`
            # docstring. For email events this re-downloads attachments; an
            # acceptable cost at the current low volume, not worth a schema
            # change to cache it.
            body = json.dumps(
                _decode_payload(event.raw_payload, sources.get(event.source_id))
            )
            resp = requests.post(
                rule.action_url, data=body, headers=headers, timeout=30
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
