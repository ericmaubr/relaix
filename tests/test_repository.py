from __future__ import annotations

from relaix.repository import (
    EventRepository,
    PollingLogRepository,
    RuleExecutionRepository,
    RuleRepository,
    SourceRepository,
)


def test_create_and_get_source():
    repo = SourceRepository()
    source = repo.create(
        name="webhook.site - example", api_url="https://webhook.site/token/abc/requests"
    )
    assert repo.get(source.id) == source
    assert source.active is True
    assert source.kind == "webhook_site"


def test_list_sources_ordered_by_name():
    repo = SourceRepository()
    repo.create(name="Zulu", api_url="https://example.com/z")
    repo.create(name="Alpha", api_url="https://example.com/a")
    names = [s.name for s in repo.list()]
    assert names == ["Alpha", "Zulu"]


def test_update_source():
    repo = SourceRepository()
    source = repo.create(name="Source", api_url="https://example.com")
    updated = repo.update(source.id, active=False)
    assert updated.active is False
    assert updated.name == source.name


def test_update_missing_source_returns_none():
    repo = SourceRepository()
    assert repo.update("does-not-exist", active=False) is None


def test_delete_source():
    repo = SourceRepository()
    source = repo.create(name="Source", api_url="https://example.com")
    assert repo.delete(source.id) is True
    assert repo.get(source.id) is None
    assert repo.delete(source.id) is False


def test_create_rule_with_conditions():
    sources = SourceRepository()
    rules = RuleRepository()
    source = sources.create(name="Source", api_url="https://example.com")
    rule = rules.create(
        name="Rule A",
        source_id=source.id,
        action_url="https://internal/action",
        conditions=[
            {"field_path": "message.name", "operator": "=", "value": "expected"},
            {
                "field_path": "message.task.name",
                "operator": "contains",
                "value": "PGDAS",
            },
        ],
    )
    conditions = rules.list_conditions(rule.id)
    assert len(conditions) == 2
    assert {c.field_path for c in conditions} == {"message.name", "message.task.name"}


def test_replace_rule_conditions():
    sources = SourceRepository()
    rules = RuleRepository()
    source = sources.create(name="Source", api_url="https://example.com")
    rule = rules.create(
        name="Rule A", source_id=source.id, action_url="https://internal/action"
    )
    assert rules.list_conditions(rule.id) == []
    rules.replace_conditions(
        rule.id, [{"field_path": "message.name", "operator": "=", "value": "x"}]
    )
    assert len(rules.list_conditions(rule.id)) == 1
    rules.replace_conditions(rule.id, [])
    assert rules.list_conditions(rule.id) == []


def test_delete_rule_also_deletes_conditions():
    sources = SourceRepository()
    rules = RuleRepository()
    source = sources.create(name="Source", api_url="https://example.com")
    rule = rules.create(
        name="Rule A",
        source_id=source.id,
        action_url="https://internal/action",
        conditions=[{"field_path": "message.name", "operator": "=", "value": "x"}],
    )
    assert rules.delete(rule.id) is True
    assert rules.get(rule.id) is None


def test_event_and_polling_log_and_rule_execution_repositories_are_empty_by_default():
    sources = SourceRepository()
    source = sources.create(name="Source", api_url="https://example.com")
    assert EventRepository().list(source.id) == []
    assert PollingLogRepository().list(source.id) == []
    assert RuleExecutionRepository().list() == []


def test_create_event_and_polling_log():
    sources = SourceRepository()
    source = sources.create(name="Source", api_url="https://example.com")

    event = EventRepository().create(source.id, "ext-1", '{"foo": "bar"}')
    assert event.status == "pending"
    assert EventRepository().get(event.id) == event

    log = PollingLogRepository().create(source.id, success=True, new_events_found=1)
    assert log.success is True
    assert PollingLogRepository().list(source.id) == [log]
