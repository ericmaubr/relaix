"""Entry point: python -m relaix <command> [options]"""

from __future__ import annotations

import sys

from relaix.version import handle_version_flags

_COMMANDS = (
    "serve",
    "provision-db",
    "migrate",
    "collect",
    "execute",
)


def main() -> None:
    code = handle_version_flags()
    if code is not None:
        sys.exit(code)

    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        sys.exit(0 if argv else 1)

    command = argv[0].lower()
    rest = argv[1:]

    if command == "serve":
        from relaix.cli.serve import main_serve

        sys.exit(main_serve(rest))
    elif command == "provision-db":
        from relaix.cli.provision_db import main_provision_db

        sys.exit(main_provision_db(rest))
    elif command == "migrate":
        from relaix.cli.migrate import main_migrate

        sys.exit(main_migrate(rest))
    elif command == "collect":
        from relaix.cli.collect import main_collect

        sys.exit(main_collect(rest))
    elif command == "execute":
        from relaix.cli.execute import main_execute

        sys.exit(main_execute(rest))
    else:
        print(f"Unknown command: {command}")
        print(f"Available commands: {', '.join(_COMMANDS)}")
        sys.exit(1)


def _usage() -> None:
    print("Usage: python -m relaix <command> [options]")
    print()
    print("Commands:")
    print("  serve          Starts the HTTP API (FastAPI)")
    print("                   [--host TEXT]        host (default: 127.0.0.1 or")
    print("                                        api.conf)")
    print("                   [--port INT]         port (default: 8790 or api.conf)")
    print("                   [--api-token TOKEN]  bearer token required on the")
    print("                                        endpoints")
    print()
    print("  provision-db   Creates (idempotently) role + databases on Postgres")
    print("                   [--host] [--port] [--admin-user] [--admin-password]")
    print("                   [--role] [--role-password] [--database]")
    print("                   [--test-database] [--no-test-database]")
    print("                   [--recreate-password]")
    print()
    print("  migrate        Applies the schema up to the latest version (Alembic")
    print(
        "                 upgrade head) — uses the packaged scripts, no repo checkout"
    )
    print("                 needed. Run after every deploy/update.")
    print()
    print("  collect        Polls active sources for new events (Collector)")
    print("                   [--once]             run one cycle and exit")
    print("                   [--interval SECONDS] sleep between cycles (default: 60)")
    print()
    print("  execute        Matches events against rules and dispatches actions")
    print("                 (Executor)")
    print("                   [--once]             run one cycle and exit")
    print("                   [--interval SECONDS] sleep between cycles (default: 30)")
    print()
    print("Database flags (commands that access data):")
    print("  --db-url URL   SQLAlchemy connection string — takes precedence over")
    print("                 everything")
    print("  --conf FILE    api.conf to use if --db-url and the DATABASE_URL env var")
    print("                 aren't given (default: api.conf in the current directory)")
    print("  With none of the three: uses SQLite at ~/.relaix/relaix.db")
    print()
    print("Global flags: --version, --about, --help/-h")


if __name__ == "__main__":
    main()
