"""Domain dataclasses — plain data, no persistence logic here."""

from __future__ import annotations

from dataclasses import dataclass

VALID_OPERATORS = frozenset(
    {"=", "!=", "contains", "not_contains", ">", ">=", "<", "<="}
)


@dataclass
class WebhookSource:
    id: str
    name: str
    kind: str
    api_url: str
    api_token: str | None
    channel_id: str | None
    polling_interval_seconds: int
    last_processed_cursor: str | None
    active: bool
    created_at: str
    updated_at: str


@dataclass
class WebhookPollingLog:
    id: str
    source_id: str
    executed_at: str
    success: bool
    new_events_found: int
    error_detail: str | None
    duration_ms: int | None


@dataclass
class WebhookEvent:
    id: str
    source_id: str
    external_id: str
    raw_payload: str
    received_at: str
    status: str
    attempts: int
    updated_at: str | None


@dataclass
class WebhookRule:
    id: str
    name: str
    source_id: str
    active: bool
    action_url: str
    action_token: str | None
    created_at: str
    updated_at: str


@dataclass
class WebhookRuleCondition:
    id: str
    rule_id: str
    group_index: int
    field_path: str
    operator: str
    value: str


@dataclass
class WebhookRuleExecution:
    id: str
    event_id: str
    rule_id: str
    status: str
    attempts: int
    response_http_status: int | None
    response_detail: str | None
    executed_at: str | None
    updated_at: str | None
