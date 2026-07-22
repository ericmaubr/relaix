"""Helpers shared across CLI subcommands."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def add_db_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db-url",
        metavar="URL",
        help=(
            "SQLAlchemy connection string (e.g. sqlite:///path.db, "
            "postgresql+psycopg://user:password@host/db). Takes precedence "
            "over everything."
        ),
    )
    parser.add_argument(
        "--conf",
        metavar="FILE",
        type=Path,
        default=Path("api.conf"),
        help=(
            "api.conf file — used if --db-url and the DATABASE_URL env var "
            "aren't given (default: api.conf in the current directory)"
        ),
    )


def configure_db(args: argparse.Namespace) -> None:
    """Resolves the database URL in order: --db-url > env DATABASE_URL >
    api.conf ([db] url) > local SQLite default, and configures `db.py`."""
    from relaix import db

    if args.db_url:
        db.set_database_url(args.db_url)
        return
    if os.environ.get("DATABASE_URL"):
        return  # db.get_database_url() reads the env var on its own
    conf_path: Path = args.conf
    if conf_path and conf_path.exists():
        from relaix.conf import load_api_conf

        conf = load_api_conf(conf_path)
        if conf.db_url:
            db.set_database_url(conf.db_url)
