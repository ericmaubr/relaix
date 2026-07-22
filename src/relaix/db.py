"""SQLAlchemy engine and schema.

Schema defined as `Table`/`Column` (SQLAlchemy Core, not ORM), portable
between SQLite (dev/test) and Postgres (production). `metadata` is the single
source of truth — the Alembic migrations under `alembic/versions/` are
generated from it and must never drift from it.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    Engine,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
)
from sqlalchemy.pool import StaticPool

_DEFAULT_DIR = Path.home() / ".relaix"
_DEFAULT_SQLITE_PATH = _DEFAULT_DIR / "relaix.db"

metadata = MetaData()

webhook_source = Table(
    "webhook_source",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("kind", String, nullable=False, server_default="webhook_site"),
    Column("api_url", String, nullable=False),
    Column("api_token", String),
    Column("channel_id", String),
    Column("polling_interval_seconds", Integer, nullable=False, server_default="300"),
    Column("last_processed_cursor", String),
    Column("active", Boolean, nullable=False, server_default="1"),
    Column("created_at", String),
    Column("updated_at", String),
)

webhook_polling_log = Table(
    "webhook_polling_log",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, ForeignKey("webhook_source.id"), nullable=False),
    Column("executed_at", String, nullable=False),
    Column("success", Boolean, nullable=False),
    Column("new_events_found", Integer, nullable=False, server_default="0"),
    Column("error_detail", Text),
    Column("duration_ms", Integer),
)
Index("idx_webhook_polling_log_source", webhook_polling_log.c.source_id)

webhook_event = Table(
    "webhook_event",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, ForeignKey("webhook_source.id"), nullable=False),
    Column("external_id", String, nullable=False),
    Column("raw_payload", Text, nullable=False),
    Column("received_at", String, nullable=False),
    Column("status", String, nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("updated_at", String),
)
Index("idx_webhook_event_source", webhook_event.c.source_id)
Index("idx_webhook_event_status", webhook_event.c.status)
Index(
    "idx_webhook_event_source_external_id",
    webhook_event.c.source_id,
    webhook_event.c.external_id,
    unique=True,
)

webhook_rule = Table(
    "webhook_rule",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("source_id", String, ForeignKey("webhook_source.id"), nullable=False),
    Column("active", Boolean, nullable=False, server_default="1"),
    Column("action_url", String, nullable=False),
    Column("action_token", String),
    Column("created_at", String),
    Column("updated_at", String),
)
Index("idx_webhook_rule_source", webhook_rule.c.source_id)

webhook_rule_condition = Table(
    "webhook_rule_condition",
    metadata,
    Column("id", String, primary_key=True),
    Column("rule_id", String, ForeignKey("webhook_rule.id"), nullable=False),
    # AND within the same group_index; OR across different groups (only
    # group 0 is evaluated today — see README "Out of scope").
    Column("group_index", Integer, nullable=False, server_default="0"),
    Column("field_path", String, nullable=False),
    Column("operator", String, nullable=False),
    Column("value", String, nullable=False),
)
Index("idx_webhook_rule_condition_rule", webhook_rule_condition.c.rule_id)

webhook_rule_execution = Table(
    "webhook_rule_execution",
    metadata,
    Column("id", String, primary_key=True),
    Column("event_id", String, ForeignKey("webhook_event.id"), nullable=False),
    Column("rule_id", String, ForeignKey("webhook_rule.id"), nullable=False),
    Column("status", String, nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("response_http_status", Integer),
    Column("response_detail", Text),
    Column("executed_at", String),
    Column("updated_at", String),
)
Index("idx_webhook_rule_execution_event", webhook_rule_execution.c.event_id)
Index("idx_webhook_rule_execution_rule", webhook_rule_execution.c.rule_id)
Index("idx_webhook_rule_execution_status", webhook_rule_execution.c.status)


_database_url_override: str | None = None
_engine: Engine | None = None


def set_database_url(url: str) -> None:
    """Sets the connection string. Called by the CLI (--db-url, or resolved
    from api.conf / env var) and by tests. Takes precedence over everything."""
    global _database_url_override, _engine
    _database_url_override = url
    _engine = None  # forces a fresh Engine on the next get_engine() call


def get_database_url() -> str:
    """Resolution order when nobody called `set_database_url` explicitly:
    env var `DATABASE_URL` > local SQLite default. Reading `api.conf` happens
    earlier, in the CLI layer (`cli/_common.py`) — this module knows nothing
    about config files."""
    if _database_url_override is not None:
        return _database_url_override
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{_DEFAULT_SQLITE_PATH}"


def get_engine() -> Engine:
    """One engine per process, with connection pooling — we don't open a new
    connection per call (expensive on Postgres)."""
    global _engine
    if _engine is None:
        url = get_database_url()
        kwargs: dict = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                # SQLAlchemy's default SingletonThreadPool for :memory: gives
                # one connection per thread — since FastAPI runs sync
                # handlers on a threadpool, each request would see a
                # different in-memory database. StaticPool forces a single
                # shared connection.
                kwargs["poolclass"] = StaticPool
        else:
            kwargs["pool_pre_ping"] = True
        _engine = create_engine(url, **kwargs)
        if _engine.dialect.name == "sqlite":

            @event.listens_for(_engine, "connect")
            def _enable_foreign_keys(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def create_schema(engine: Engine | None = None) -> None:
    """Creates all tables via `metadata.create_all()` — used only by tests
    (ephemeral database, no need for migration history). On persistent
    databases (dev/production), the official schema evolution path is
    `python -m relaix migrate` (Alembic upgrade head, see `migrations.py`),
    not this function."""
    metadata.create_all(engine or get_engine())
