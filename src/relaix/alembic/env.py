"""Alembic env.py — runs in two different contexts:

1. Dev, via the `alembic` CLI from the repo root (uses the root
   `alembic.ini`, only for `alembic revision --autogenerate` when creating a
   new migration).
2. Production, via `python -m relaix migrate` (`migrations.py:upgrade_head`),
   which builds a `Config()` without any `.ini` file — only `script_location`
   set programmatically.

In neither case does the database URL come from `sqlalchemy.url` in the ini
(which doesn't even exist in case 2). Actual resolution, in the same order
the CLI uses (`cli/_common.py`): explicit override (`db.set_database_url`,
already called before either of the two commands above invokes Alembic) >
env var DATABASE_URL > api.conf ([db] url, looked up in the current
directory — only relevant if nothing called the override first) > local
SQLite default."""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from relaix.db import get_database_url, metadata  # noqa: E402

target_metadata = metadata


def _resolve_url() -> str:
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    conf_path = Path("api.conf")
    if conf_path.exists():
        from relaix.conf import load_api_conf

        conf = load_api_conf(conf_path)
        if conf.db_url:
            return conf.db_url
    return get_database_url()


def run_migrations_offline() -> None:
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
