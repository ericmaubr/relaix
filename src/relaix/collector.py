"""Collector — pulls new events from each active source and records them,
independently of rule evaluation (see plan §2.2/§2.3: pull via provider API,
no inbound port; Collector and Executor are decoupled processes).

Only the `webhook_site` source kind is implemented — see README "Out of
scope"."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import requests
from sqlalchemy.exc import IntegrityError

from relaix.domain import WebhookSource
from relaix.repository import EventRepository, PollingLogRepository, SourceRepository

FetchFn = Callable[[WebhookSource], list[dict]]


class CollectorError(RuntimeError):
    pass


def fetch_webhook_site_requests(source: WebhookSource) -> list[dict]:
    """Fetches requests from a webhook.site token via its API, newest first.
    `api_url` is the provider's base URL (e.g. `https://webhook.site`),
    `channel_id` is the token id, `api_token` is the account's API key.

    Newest-first (not oldest) matters: `poll_source` stops as soon as it
    hits an item already covered by the cursor, so this bounds the fetch to
    just the new items regardless of how much history the token has —
    oldest-first with a single page would silently stop seeing new events
    once the token passed `per_page` total requests."""
    url = f"{source.api_url.rstrip('/')}/token/{source.channel_id}/requests"
    headers = {"Api-Key": source.api_token} if source.api_token else {}
    resp = requests.get(
        url, headers=headers, params={"sorting": "newest", "per_page": 100}, timeout=15
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


_FETCHERS: dict[str, FetchFn] = {"webhook_site": fetch_webhook_site_requests}


def poll_source(source: WebhookSource, fetch_fn: FetchFn | None = None) -> dict:
    """Runs one polling cycle for a single source: fetches items from the
    provider, records genuinely new ones as `webhook_event` rows (before any
    rule evaluation — see plan §2.3), and writes one `webhook_polling_log`
    row for the cycle either way."""
    fetch = fetch_fn or _FETCHERS.get(source.kind)
    if fetch is None:
        raise CollectorError(
            f"No collector implemented for source kind {source.kind!r}"
        )

    events = EventRepository()
    logs = PollingLogRepository()
    started = time.monotonic()

    try:
        items = fetch(source)
    except Exception as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        logs.create(
            source.id, success=False, error_detail=str(e), duration_ms=duration_ms
        )
        raise CollectorError(str(e)) from e

    cursor = source.last_processed_cursor
    newest_cursor = cursor
    new_count = 0

    for item in items:  # newest first — stop at the first already-seen item
        created_at = item.get("created_at", "")
        if cursor and created_at and created_at <= cursor:
            break
        external_id = item.get("uuid") or item.get("id")
        if not external_id:
            continue
        raw_payload = item.get("content") or json.dumps(item)
        try:
            events.create(source.id, str(external_id), raw_payload)
            new_count += 1
        except IntegrityError:
            pass  # already recorded (duplicate external_id) — safe to skip
        if created_at and (newest_cursor is None or created_at > newest_cursor):
            newest_cursor = created_at

    if newest_cursor != cursor:
        SourceRepository().update(source.id, last_processed_cursor=newest_cursor)

    duration_ms = int((time.monotonic() - started) * 1000)
    log = logs.create(
        source.id, success=True, new_events_found=new_count, duration_ms=duration_ms
    )
    return {"source_id": source.id, "new_events_found": new_count, "log_id": log.id}


def _due_for_polling(source: WebhookSource) -> bool:
    last = PollingLogRepository().list(source.id, limit=1)
    if not last:
        return True
    executed_at = datetime.strptime(last[0].executed_at, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=UTC
    )
    return datetime.now(UTC) - executed_at >= timedelta(
        seconds=source.polling_interval_seconds
    )


def poll_all_active_sources() -> list[dict]:
    """Polls every active source whose `polling_interval_seconds` has
    elapsed since its last polling attempt. Meant to be invoked on a short,
    fixed schedule (e.g. every minute) — sources with a longer interval are
    simply skipped until due."""
    results = []
    for source in SourceRepository().list():
        if not source.active or not _due_for_polling(source):
            continue
        try:
            results.append(poll_source(source))
        except CollectorError:
            # already logged in webhook_polling_log — keep going for other sources
            continue
    return results
