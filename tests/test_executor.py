from __future__ import annotations

import json

from relaix.executor import dispatch_pending_executions, evaluate_pending_events
from relaix.repository import (
    EventRepository,
    RuleExecutionRepository,
    RuleRepository,
    SourceRepository,
)


def _make_source():
    return SourceRepository().create(name="Source", api_url="https://example.com")


def _make_rule(source_id, conditions):
    return RuleRepository().create(
        name="Rule",
        source_id=source_id,
        action_url="https://internal/action",
        conditions=conditions,
    )


def _make_event(source_id, payload):
    return EventRepository().create(source_id, "ext-1", json.dumps(payload))


def test_evaluate_pending_events_creates_execution_for_matching_rule():
    source = _make_source()
    rule = _make_rule(
        source.id,
        [{"field_path": "message.name", "operator": "=", "value": "expected"}],
    )
    event = _make_event(source.id, {"message": {"name": "expected"}})

    result = evaluate_pending_events()

    assert result == {"events_processed": 1, "rules_matched": 1}
    assert EventRepository().get(event.id).status == "done"
    executions = RuleExecutionRepository().list(event_id=event.id)
    assert len(executions) == 1
    assert executions[0].rule_id == rule.id
    assert executions[0].status == "pending"


def test_evaluate_pending_events_skips_non_matching_rule():
    source = _make_source()
    _make_rule(
        source.id, [{"field_path": "message.name", "operator": "=", "value": "other"}]
    )
    event = _make_event(source.id, {"message": {"name": "expected"}})

    result = evaluate_pending_events()

    assert result == {"events_processed": 1, "rules_matched": 0}
    assert EventRepository().get(event.id).status == "done"
    assert RuleExecutionRepository().list(event_id=event.id) == []


def test_evaluate_pending_events_skips_inactive_rule():
    source = _make_source()
    rule = _make_rule(
        source.id,
        [{"field_path": "message.name", "operator": "=", "value": "expected"}],
    )
    RuleRepository().update(rule.id, active=False)
    event = _make_event(source.id, {"message": {"name": "expected"}})

    result = evaluate_pending_events()

    assert result["rules_matched"] == 0
    assert RuleExecutionRepository().list(event_id=event.id) == []


def test_evaluate_pending_events_marks_invalid_json_as_error():
    source = _make_source()
    event = EventRepository().create(source.id, "ext-1", "not json")

    evaluate_pending_events()

    assert EventRepository().get(event.id).status == "error"


def test_evaluate_pending_events_stops_retrying_malformed_content_at_source_cap():
    source = SourceRepository().create(
        name="Source", api_url="https://example.com", max_content_attempts=2
    )
    event = EventRepository().create(source.id, "ext-1", "not json")

    evaluate_pending_events()  # attempt 1 -> error
    assert EventRepository().get(event.id).attempts == 1

    evaluate_pending_events()  # attempt 2 -> error, now at the cap
    assert EventRepository().get(event.id).attempts == 2

    result = evaluate_pending_events()  # capped — must not attempt a 3rd time
    assert result == {"events_processed": 0, "rules_matched": 0}
    assert EventRepository().get(event.id).attempts == 2


def test_evaluate_pending_events_is_idempotent_for_already_matched_event():
    source = _make_source()
    rule = _make_rule(
        source.id,
        [{"field_path": "message.name", "operator": "=", "value": "expected"}],
    )
    event = _make_event(source.id, {"message": {"name": "expected"}})

    evaluate_pending_events()
    # event is now "done" — re-running must not create a duplicate execution
    evaluate_pending_events()

    executions = RuleExecutionRepository().list(event_id=event.id, rule_id=rule.id)
    assert len(executions) == 1


def test_dispatch_pending_executions_success(monkeypatch):
    source = _make_source()
    rule = _make_rule(
        source.id,
        [{"field_path": "message.name", "operator": "=", "value": "expected"}],
    )
    event = _make_event(source.id, {"message": {"name": "expected"}})
    evaluate_pending_events()

    class FakeResponse:
        ok = True
        status_code = 200
        text = '{"result": "ok"}'

    def fake_post(url, data=None, headers=None, timeout=None):
        assert url == rule.action_url
        return FakeResponse()

    monkeypatch.setattr("relaix.executor.requests.post", fake_post)

    result = dispatch_pending_executions()

    assert result == {"dispatched": 1, "succeeded": 1}
    execution = RuleExecutionRepository().list(event_id=event.id)[0]
    assert execution.status == "success"
    assert execution.response_http_status == 200
    assert execution.attempts == 1


def test_dispatch_pending_executions_marks_error_on_bad_status(monkeypatch):
    source = _make_source()
    _make_rule(
        source.id,
        [{"field_path": "message.name", "operator": "=", "value": "expected"}],
    )
    event = _make_event(source.id, {"message": {"name": "expected"}})
    evaluate_pending_events()

    class FakeResponse:
        ok = False
        status_code = 500
        text = "boom"

    monkeypatch.setattr(
        "relaix.executor.requests.post", lambda *a, **kw: FakeResponse()
    )

    result = dispatch_pending_executions()

    assert result == {"dispatched": 1, "succeeded": 0}
    execution = RuleExecutionRepository().list(event_id=event.id)[0]
    assert execution.status == "error"


def test_dispatch_pending_executions_retries_error_executions(monkeypatch):
    source = _make_source()
    _make_rule(
        source.id,
        [{"field_path": "message.name", "operator": "=", "value": "expected"}],
    )
    event = _make_event(source.id, {"message": {"name": "expected"}})
    evaluate_pending_events()

    import relaix.executor as executor_module

    monkeypatch.setattr(
        executor_module.requests,
        "post",
        lambda *a, **kw: (_ for _ in ()).throw(
            executor_module.requests.RequestException("timeout")
        ),
    )
    dispatch_pending_executions()
    execution = RuleExecutionRepository().list(event_id=event.id)[0]
    assert execution.status == "error"
    assert execution.attempts == 1

    class FakeResponse:
        ok = True
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        executor_module.requests, "post", lambda *a, **kw: FakeResponse()
    )
    result = dispatch_pending_executions()

    assert result == {"dispatched": 1, "succeeded": 1}
    execution = RuleExecutionRepository().list(event_id=event.id)[0]
    assert execution.status == "success"
    assert execution.attempts == 2
