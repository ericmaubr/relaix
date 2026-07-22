"""Applies Alembic migrations from the scripts packaged under
`relaix/alembic/` (`env.py`, `versions/*.py`) — no repo checkout or
`alembic.ini` on disk required. This is what
`python -m relaix migrate` calls, and it's the official path in production
(`pip install relaix` alone is enough)."""

from __future__ import annotations

import importlib.resources

from alembic import command
from alembic.config import Config


def upgrade_head() -> None:
    with importlib.resources.as_file(
        importlib.resources.files("relaix") / "alembic"
    ) as script_location:
        cfg = Config()
        cfg.set_main_option("script_location", str(script_location))
        command.upgrade(cfg, "head")
