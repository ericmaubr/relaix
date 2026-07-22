"""CLI: python -m relaix migrate

Applies the schema up to the latest version (Alembic `upgrade head`) using
the migration scripts packaged with the module — no repo checkout needed,
just `pip install relaix`."""

from __future__ import annotations

import argparse

from relaix.cli._common import add_db_arguments, configure_db


def main_migrate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="relaix migrate")
    add_db_arguments(parser)
    args = parser.parse_args(argv)
    configure_db(args)

    from relaix.migrations import upgrade_head

    upgrade_head()
    print("Schema up to date (alembic upgrade head).")
    return 0
