"""Inline check for a stale schema — relaix is deliberately independent and
must NOT depend on conta_tools_shared (explicit decision, 2026-09-05).

Same contract as conta_tools_shared.migracao.avisar_migracao_pendente:
compares the `alembic_version` row in the DB against the head of the
packaged alembic scripts, logs CRITICAL when they diverge, and returns
True/False/None (None = the check itself failed). Best-effort only — must
never raise, never blocks boot.

Origin: ecosystem audit 2026-09, item 6."""

from __future__ import annotations

import importlib.resources
import logging


def check_migracao_pendente() -> bool | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        from relaix.db import get_engine

        with importlib.resources.as_file(
            importlib.resources.files("relaix") / "alembic"
        ) as script_location:
            cfg = Config()
            cfg.set_main_option("script_location", str(script_location))
            head = ScriptDirectory.from_config(cfg).get_current_head() or ""

        engine = get_engine()
        try:
            with engine.connect() as conn:
                atual = (
                    conn.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    ).scalar()
                    or ""
                )
        except Exception:
            atual = ""  # table missing = never migrated

        pendente = atual != head
        if pendente:
            logging.getLogger(__name__).critical(
                "OUTDATED DATABASE (relaix): db at %s, code expects %s. Run: "
                "python -m relaix migrate",
                atual or "(never migrated)", head,
            )
        return pendente
    except Exception:
        logging.getLogger(__name__).warning(
            "migration check failed", exc_info=True
        )
        return None
