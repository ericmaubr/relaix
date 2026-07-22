from __future__ import annotations

import pytest

from relaix.collector import CollectorError, poll_all_active_sources, poll_source
from relaix.repository import EventRepository, PollingLogRepository, SourceRepository


def _make_source(**overrides):
    fields = dict(
        name="webhook.site - test",
        api_url="https://webhook.site",
        kind="webhook_site",
        api_token="key-123",
        channel_id="token-abc",
        polling_interval_seconds=300,
    )
    fields.update(overrides)
    return SourceRepository().create(**fields)


def test_poll_source_records_new_events_and_a_success_log():
    source = _make_source()
    items = [
        {"uuid": "req-2", "created_at": "2026-07-22T10:01:00", "content": '{"a": 2}'},
        {"uuid": "req-1", "created_at": "2026-07-22T10:00:00", "content": '{"a": 1}'},
    ]

    result = poll_source(source, fetch_fn=lambda s: items)

    assert result["new_events_found"] == 2
    events = EventRepository().list(source.id)
    assert {e.external_id for e in events} == {"req-1", "req-2"}

    logs = PollingLogRepository().list(source.id)
    assert len(logs) == 1
    assert logs[0].success is True
    assert logs[0].new_events_found == 2

    updated_source = SourceRepository().get(source.id)
    assert updated_source.last_processed_cursor == "2026-07-22T10:01:00"


def test_poll_source_skips_items_already_seen_via_cursor():
    source = _make_source()
    items = [{"uuid": "req-1", "created_at": "2026-07-22T10:00:00", "content": "{}"}]
    poll_source(source, fetch_fn=lambda s: items)

    source = SourceRepository().get(source.id)
    result = poll_source(source, fetch_fn=lambda s: items)

    assert result["new_events_found"] == 0
    assert len(EventRepository().list(source.id)) == 1


def test_poll_source_stops_at_first_already_seen_item_newest_first():
    source = _make_source()
    first_batch = [
        {"uuid": "req-1", "created_at": "2026-07-22T10:00:00", "content": "{}"}
    ]
    poll_source(source, fetch_fn=lambda s: first_batch)
    source = SourceRepository().get(source.id)

    # newest-first: two new items, then the already-seen one — must stop there
    # without needing req-1 to be absent or paginated around.
    fetched = []

    def fetch_fn(s):
        fetched.append(1)
        return [
            {"uuid": "req-3", "created_at": "2026-07-22T10:02:00", "content": "{}"},
            {"uuid": "req-2", "created_at": "2026-07-22T10:01:00", "content": "{}"},
            {"uuid": "req-1", "created_at": "2026-07-22T10:00:00", "content": "{}"},
        ]

    result = poll_source(source, fetch_fn=fetch_fn)

    assert result["new_events_found"] == 2
    assert {e.external_id for e in EventRepository().list(source.id)} == {
        "req-1",
        "req-2",
        "req-3",
    }
    updated_source = SourceRepository().get(source.id)
    assert updated_source.last_processed_cursor == "2026-07-22T10:02:00"


def test_poll_source_skips_duplicate_external_id_even_without_cursor_advance():
    source = _make_source()
    items = [
        {"uuid": "req-1", "created_at": "2026-07-22T10:00:00", "content": "{}"},
        {"uuid": "req-1", "created_at": "2026-07-22T10:00:00", "content": "{}"},
    ]
    result = poll_source(source, fetch_fn=lambda s: items)

    assert result["new_events_found"] == 1
    assert len(EventRepository().list(source.id)) == 1


def test_poll_source_logs_failure_and_raises_on_fetch_error():
    source = _make_source()

    def _boom(_source):
        raise RuntimeError("provider unreachable")

    with pytest.raises(CollectorError):
        poll_source(source, fetch_fn=_boom)

    logs = PollingLogRepository().list(source.id)
    assert len(logs) == 1
    assert logs[0].success is False
    assert "provider unreachable" in logs[0].error_detail


def test_poll_source_unknown_kind_raises():
    source = _make_source(kind="unsupported")
    with pytest.raises(CollectorError):
        poll_source(source)


def test_poll_all_active_sources_skips_inactive_and_not_due(monkeypatch):
    active_due = _make_source(name="Active Due", polling_interval_seconds=0)
    inactive = _make_source(name="Inactive")
    SourceRepository().update(inactive.id, active=False)

    calls = []

    def fake_fetch(source):
        calls.append(source.id)
        return []

    import relaix.collector as collector_module

    monkeypatch.setitem(collector_module._FETCHERS, "webhook_site", fake_fetch)

    results = poll_all_active_sources()

    assert active_due.id in calls
    assert inactive.id not in calls
    assert len(results) == 1


def test_poll_all_active_sources_skips_source_not_yet_due(monkeypatch):
    source = _make_source(name="Not due yet", polling_interval_seconds=3600)
    poll_source(source, fetch_fn=lambda s: [])  # first cycle always due (no prior log)

    calls = []
    monkeypatch.setattr(
        "relaix.collector._FETCHERS",
        {"webhook_site": lambda s: calls.append(s.id) or []},
    )

    results = poll_all_active_sources()

    assert calls == []
    assert results == []
