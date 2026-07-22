"""Data access: webhook_source, webhook_rule (+conditions), webhook_event,
webhook_polling_log, webhook_rule_execution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, insert, select, update

from relaix.db import (
    get_engine,
)
from relaix.db import (
    webhook_event as t_event,
)
from relaix.db import (
    webhook_polling_log as t_polling_log,
)
from relaix.db import (
    webhook_rule as t_rule,
)
from relaix.db import (
    webhook_rule_condition as t_rule_condition,
)
from relaix.db import (
    webhook_rule_execution as t_rule_execution,
)
from relaix.db import (
    webhook_source as t_source,
)
from relaix.domain import (
    WebhookEvent,
    WebhookPollingLog,
    WebhookRule,
    WebhookRuleCondition,
    WebhookRuleExecution,
    WebhookSource,
)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_source(row) -> WebhookSource:
    m = row._mapping
    return WebhookSource(
        id=m["id"],
        name=m["name"],
        kind=m["kind"],
        api_url=m["api_url"],
        api_token=m["api_token"],
        channel_id=m["channel_id"],
        polling_interval_seconds=m["polling_interval_seconds"],
        last_processed_cursor=m["last_processed_cursor"],
        active=bool(m["active"]),
        created_at=m["created_at"] or "",
        updated_at=m["updated_at"] or "",
    )


def _row_to_rule(row) -> WebhookRule:
    m = row._mapping
    return WebhookRule(
        id=m["id"],
        name=m["name"],
        source_id=m["source_id"],
        active=bool(m["active"]),
        action_url=m["action_url"],
        action_token=m["action_token"],
        created_at=m["created_at"] or "",
        updated_at=m["updated_at"] or "",
    )


def _row_to_rule_condition(row) -> WebhookRuleCondition:
    m = row._mapping
    return WebhookRuleCondition(
        id=m["id"],
        rule_id=m["rule_id"],
        group_index=m["group_index"],
        field_path=m["field_path"],
        operator=m["operator"],
        value=m["value"],
    )


def _row_to_event(row) -> WebhookEvent:
    m = row._mapping
    return WebhookEvent(
        id=m["id"],
        source_id=m["source_id"],
        external_id=m["external_id"],
        raw_payload=m["raw_payload"],
        received_at=m["received_at"],
        status=m["status"],
        attempts=m["attempts"],
        updated_at=m["updated_at"],
    )


def _row_to_polling_log(row) -> WebhookPollingLog:
    m = row._mapping
    return WebhookPollingLog(
        id=m["id"],
        source_id=m["source_id"],
        executed_at=m["executed_at"],
        success=bool(m["success"]),
        new_events_found=m["new_events_found"],
        error_detail=m["error_detail"],
        duration_ms=m["duration_ms"],
    )


def _row_to_rule_execution(row) -> WebhookRuleExecution:
    m = row._mapping
    return WebhookRuleExecution(
        id=m["id"],
        event_id=m["event_id"],
        rule_id=m["rule_id"],
        status=m["status"],
        attempts=m["attempts"],
        response_http_status=m["response_http_status"],
        response_detail=m["response_detail"],
        executed_at=m["executed_at"],
        updated_at=m["updated_at"],
    )


class SourceRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def create(
        self,
        name: str,
        api_url: str,
        kind: str = "webhook_site",
        api_token: str | None = None,
        channel_id: str | None = None,
        polling_interval_seconds: int = 300,
    ) -> WebhookSource:
        now = _now()
        values = dict(
            id=_new_id(),
            name=name,
            kind=kind,
            api_url=api_url,
            api_token=api_token,
            channel_id=channel_id,
            polling_interval_seconds=polling_interval_seconds,
            last_processed_cursor=None,
            active=True,
            created_at=now,
            updated_at=now,
        )
        with self._engine.begin() as conn:
            conn.execute(insert(t_source).values(**values))
        return self.get(values["id"])

    def get(self, source_id: str) -> WebhookSource | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(t_source).where(t_source.c.id == source_id)
            ).fetchone()
        return _row_to_source(row) if row else None

    def list(self) -> list[WebhookSource]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(t_source).order_by(t_source.c.name)).fetchall()
        return [_row_to_source(r) for r in rows]

    def update(self, source_id: str, **fields) -> WebhookSource | None:
        if not fields:
            return self.get(source_id)
        fields["updated_at"] = _now()
        with self._engine.begin() as conn:
            result = conn.execute(
                update(t_source).where(t_source.c.id == source_id).values(**fields)
            )
            if result.rowcount == 0:
                return None
        return self.get(source_id)

    def delete(self, source_id: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(delete(t_source).where(t_source.c.id == source_id))
        return result.rowcount > 0


class RuleRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def create(
        self,
        name: str,
        source_id: str,
        action_url: str,
        action_token: str | None = None,
        conditions: list[dict] | None = None,
    ) -> WebhookRule:
        now = _now()
        rule_id = _new_id()
        with self._engine.begin() as conn:
            conn.execute(
                insert(t_rule).values(
                    id=rule_id,
                    name=name,
                    source_id=source_id,
                    active=True,
                    action_url=action_url,
                    action_token=action_token,
                    created_at=now,
                    updated_at=now,
                )
            )
            for cond in conditions or []:
                conn.execute(
                    insert(t_rule_condition).values(
                        id=_new_id(),
                        rule_id=rule_id,
                        group_index=cond.get("group_index", 0),
                        field_path=cond["field_path"],
                        operator=cond["operator"],
                        value=cond["value"],
                    )
                )
        return self.get(rule_id)

    def get(self, rule_id: str) -> WebhookRule | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(t_rule).where(t_rule.c.id == rule_id)).fetchone()
        return _row_to_rule(row) if row else None

    def list(self, source_id: str | None = None) -> list[WebhookRule]:
        query = select(t_rule).order_by(t_rule.c.name)
        if source_id is not None:
            query = query.where(t_rule.c.source_id == source_id)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_rule(r) for r in rows]

    def update(self, rule_id: str, **fields) -> WebhookRule | None:
        if not fields:
            return self.get(rule_id)
        fields["updated_at"] = _now()
        with self._engine.begin() as conn:
            result = conn.execute(
                update(t_rule).where(t_rule.c.id == rule_id).values(**fields)
            )
            if result.rowcount == 0:
                return None
        return self.get(rule_id)

    def delete(self, rule_id: str) -> bool:
        with self._engine.begin() as conn:
            conn.execute(
                delete(t_rule_condition).where(t_rule_condition.c.rule_id == rule_id)
            )
            result = conn.execute(delete(t_rule).where(t_rule.c.id == rule_id))
        return result.rowcount > 0

    def list_conditions(self, rule_id: str) -> list[WebhookRuleCondition]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(t_rule_condition)
                .where(t_rule_condition.c.rule_id == rule_id)
                .order_by(t_rule_condition.c.group_index)
            ).fetchall()
        return [_row_to_rule_condition(r) for r in rows]

    def replace_conditions(self, rule_id: str, conditions: list[dict]) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                delete(t_rule_condition).where(t_rule_condition.c.rule_id == rule_id)
            )
            for cond in conditions:
                conn.execute(
                    insert(t_rule_condition).values(
                        id=_new_id(),
                        rule_id=rule_id,
                        group_index=cond.get("group_index", 0),
                        field_path=cond["field_path"],
                        operator=cond["operator"],
                        value=cond["value"],
                    )
                )
            conn.execute(
                update(t_rule).where(t_rule.c.id == rule_id).values(updated_at=_now())
            )


class EventRepository:
    """The inbox — one row per raw event pulled from a source. Writes are
    exercised by the Collector; `claim`/`finish` are exercised by the
    Executor (see collector.py / executor.py)."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def create(
        self, source_id: str, external_id: str, raw_payload: str
    ) -> WebhookEvent:
        now = _now()
        event_id = _new_id()
        with self._engine.begin() as conn:
            conn.execute(
                insert(t_event).values(
                    id=event_id,
                    source_id=source_id,
                    external_id=external_id,
                    raw_payload=raw_payload,
                    received_at=now,
                    status="pending",
                    attempts=0,
                    updated_at=now,
                )
            )
        return self.get(event_id)

    def get(self, event_id: str) -> WebhookEvent | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(t_event).where(t_event.c.id == event_id)
            ).fetchone()
        return _row_to_event(row) if row else None

    def list(
        self,
        source_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[WebhookEvent]:
        query = select(t_event).order_by(t_event.c.received_at.desc()).limit(limit)
        if source_id is not None:
            query = query.where(t_event.c.source_id == source_id)
        if status is not None:
            query = query.where(t_event.c.status == status)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_event(r) for r in rows]

    def claim(self, event_id: str) -> bool:
        """Atomically moves an event from pending/error to processing.
        Returns False if another worker already claimed it (or it doesn't
        exist / isn't claimable) — see plan §2.4 for why this is a
        conditional UPDATE instead of a distributed lock."""
        with self._engine.begin() as conn:
            result = conn.execute(
                update(t_event)
                .where(
                    t_event.c.id == event_id, t_event.c.status.in_(["pending", "error"])
                )
                .values(status="processing")
            )
        return result.rowcount > 0

    def finish(self, event_id: str, status: str, attempts: int) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(t_event)
                .where(t_event.c.id == event_id)
                .values(status=status, attempts=attempts, updated_at=_now())
            )

    def reset(self, event_id: str) -> bool:
        """Manual "reset to pending" for a row stuck in `processing` — the
        UI action from plan §2.6, used instead of an automatic reaper."""
        with self._engine.begin() as conn:
            result = conn.execute(
                update(t_event)
                .where(t_event.c.id == event_id, t_event.c.status == "processing")
                .values(status="pending", updated_at=_now())
            )
        return result.rowcount > 0


class PollingLogRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def create(
        self,
        source_id: str,
        success: bool,
        new_events_found: int = 0,
        error_detail: str | None = None,
        duration_ms: int | None = None,
    ) -> WebhookPollingLog:
        log_id = _new_id()
        with self._engine.begin() as conn:
            conn.execute(
                insert(t_polling_log).values(
                    id=log_id,
                    source_id=source_id,
                    executed_at=_now(),
                    success=success,
                    new_events_found=new_events_found,
                    error_detail=error_detail,
                    duration_ms=duration_ms,
                )
            )
        with self._engine.connect() as conn:
            row = conn.execute(
                select(t_polling_log).where(t_polling_log.c.id == log_id)
            ).fetchone()
        return _row_to_polling_log(row)

    def list(
        self, source_id: str | None = None, limit: int = 100
    ) -> list[WebhookPollingLog]:
        query = (
            select(t_polling_log)
            .order_by(t_polling_log.c.executed_at.desc())
            .limit(limit)
        )
        if source_id is not None:
            query = query.where(t_polling_log.c.source_id == source_id)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_polling_log(r) for r in rows]


class RuleExecutionRepository:
    """The outbox — one row per (event x rule that matched it). Writes are
    exercised by the Executor (see executor.py)."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def create(self, event_id: str, rule_id: str) -> WebhookRuleExecution:
        execution_id = _new_id()
        with self._engine.begin() as conn:
            conn.execute(
                insert(t_rule_execution).values(
                    id=execution_id,
                    event_id=event_id,
                    rule_id=rule_id,
                    status="pending",
                    attempts=0,
                    updated_at=_now(),
                )
            )
        return self.get(execution_id)

    def get(self, execution_id: str) -> WebhookRuleExecution | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(t_rule_execution).where(t_rule_execution.c.id == execution_id)
            ).fetchone()
        return _row_to_rule_execution(row) if row else None

    def list(
        self,
        event_id: str | None = None,
        rule_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[WebhookRuleExecution]:
        query = select(t_rule_execution).order_by(t_rule_execution.c.updated_at.desc())
        if event_id is not None:
            query = query.where(t_rule_execution.c.event_id == event_id)
        if rule_id is not None:
            query = query.where(t_rule_execution.c.rule_id == rule_id)
        if status is not None:
            query = query.where(t_rule_execution.c.status == status)
        if limit is not None:
            query = query.limit(limit)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_rule_execution(r) for r in rows]

    def claim(self, execution_id: str) -> bool:
        """Atomically moves an execution from pending/error to processing —
        same claim pattern as `EventRepository.claim` (see plan §2.4)."""
        with self._engine.begin() as conn:
            result = conn.execute(
                update(t_rule_execution)
                .where(
                    t_rule_execution.c.id == execution_id,
                    t_rule_execution.c.status.in_(["pending", "error"]),
                )
                .values(status="processing")
            )
        return result.rowcount > 0

    def finish(
        self,
        execution_id: str,
        status: str,
        response_http_status: int | None = None,
        response_detail: str | None = None,
    ) -> None:
        with self._engine.begin() as conn:
            current = conn.execute(
                select(t_rule_execution.c.attempts).where(
                    t_rule_execution.c.id == execution_id
                )
            ).scalar_one()
            conn.execute(
                update(t_rule_execution)
                .where(t_rule_execution.c.id == execution_id)
                .values(
                    status=status,
                    attempts=current + 1,
                    response_http_status=response_http_status,
                    response_detail=response_detail,
                    executed_at=_now(),
                    updated_at=_now(),
                )
            )

    def reset(self, execution_id: str) -> bool:
        """Manual "reset to pending" for a row stuck in `processing` — the
        UI action from plan §2.6, used instead of an automatic reaper."""
        with self._engine.begin() as conn:
            result = conn.execute(
                update(t_rule_execution)
                .where(
                    t_rule_execution.c.id == execution_id,
                    t_rule_execution.c.status == "processing",
                )
                .values(status="pending", updated_at=_now())
            )
        return result.rowcount > 0
