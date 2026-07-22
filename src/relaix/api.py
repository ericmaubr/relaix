"""Thin service layer between http_server.py and repository.py — validation
and cross-repository orchestration live here, not in the HTTP layer.

Repositories are instantiated per call, not module-level singletons — they
resolve the current engine (`db.get_engine()`) lazily, so switching database
URL (e.g. `db.set_database_url` in tests) takes effect immediately."""

from __future__ import annotations

from relaix.domain import VALID_OPERATORS
from relaix.repository import (
    EventRepository,
    PollingLogRepository,
    RuleExecutionRepository,
    RuleRepository,
    SourceRepository,
)


class InvalidConditionError(ValueError):
    pass


def _validate_conditions(conditions: list[dict]) -> None:
    for cond in conditions:
        operator = cond.get("operator")
        if operator == "<>":
            cond["operator"] = "!="
            operator = "!="
        if operator not in VALID_OPERATORS:
            raise InvalidConditionError(
                f"Invalid operator: {operator!r}. Options: {sorted(VALID_OPERATORS)}."
            )
        if not cond.get("field_path"):
            raise InvalidConditionError("field_path is required in every condition.")


# ── sources ──────────────────────────────────────────────────────────────


def list_sources():
    return SourceRepository().list()


def get_source(source_id: str):
    return SourceRepository().get(source_id)


def create_source(**fields):
    return SourceRepository().create(**fields)


def update_source(source_id: str, **fields):
    return SourceRepository().update(source_id, **fields)


def delete_source(source_id: str) -> bool:
    return SourceRepository().delete(source_id)


# ── rules ────────────────────────────────────────────────────────────────


def list_rules(source_id: str | None = None):
    return RuleRepository().list(source_id)


def get_rule(rule_id: str):
    return RuleRepository().get(rule_id)


def list_rule_conditions(rule_id: str):
    return RuleRepository().list_conditions(rule_id)


def create_rule(
    name: str,
    source_id: str,
    action_url: str,
    action_token: str | None = None,
    conditions: list[dict] | None = None,
):
    conditions = conditions or []
    _validate_conditions(conditions)
    return RuleRepository().create(
        name, source_id, action_url, action_token, conditions
    )


def update_rule(rule_id: str, **fields):
    return RuleRepository().update(rule_id, **fields)


def replace_rule_conditions(rule_id: str, conditions: list[dict]):
    _validate_conditions(conditions)
    repo = RuleRepository()
    repo.replace_conditions(rule_id, conditions)
    return repo.list_conditions(rule_id)


def delete_rule(rule_id: str) -> bool:
    return RuleRepository().delete(rule_id)


# ── events / polling log / rule executions — reads for the UI, plus the
# manual "reset to pending" action for rows stuck in processing (plan §2.6).
# All other writes are owned by the Collector/Executor jobs.────────────────


def list_events(
    source_id: str | None = None, status: str | None = None, limit: int = 100
):
    return EventRepository().list(source_id=source_id, status=status, limit=limit)


def get_event(event_id: str):
    return EventRepository().get(event_id)


def reset_event(event_id: str) -> bool:
    return EventRepository().reset(event_id)


def list_polling_log(source_id: str | None = None, limit: int = 100):
    return PollingLogRepository().list(source_id, limit)


def list_rule_executions(
    event_id: str | None = None,
    rule_id: str | None = None,
    status: str | None = None,
):
    return RuleExecutionRepository().list(
        event_id=event_id, rule_id=rule_id, status=status
    )


def reset_rule_execution(execution_id: str) -> bool:
    return RuleExecutionRepository().reset(execution_id)
