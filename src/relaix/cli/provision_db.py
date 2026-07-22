"""CLI: python -m relaix provision-db

Creates (idempotently) the application role and databases on Postgres.
Safe to re-run: if the role/databases already exist, it just confirms and
moves on — unless --recreate-password is passed, which rotates the existing
role's password."""

from __future__ import annotations

import argparse
import getpass
import re
import secrets
import string
import sys

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str, label: str) -> None:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label}: {name!r}. Use only letters, numbers and "
            "underscore, starting with a letter or underscore."
        )


def _generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main_provision_db(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="relaix provision-db")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument(
        "--admin-password",
        default=None,
        help="Admin user password (prompted interactively if omitted)",
    )
    parser.add_argument("--role", default="relaix_app")
    parser.add_argument(
        "--role-password",
        default=None,
        help="Application role password (generated if omitted and the role is new)",
    )
    parser.add_argument("--database", default="relaix")
    parser.add_argument("--test-database", default="relaix_test")
    parser.add_argument(
        "--no-test-database", action="store_true", help="Don't create the test database"
    )
    parser.add_argument(
        "--recreate-password",
        action="store_true",
        help="Rotate the role's password, even if it already exists",
    )
    args = parser.parse_args(argv)

    try:
        _validate_identifier(args.role, "--role")
        _validate_identifier(args.database, "--database")
        if not args.no_test_database:
            _validate_identifier(args.test_database, "--test-database")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    import psycopg
    from psycopg import sql

    admin_password = args.admin_password or getpass.getpass(
        f"Password for admin user '{args.admin_user}': "
    )

    try:
        conn = psycopg.connect(
            host=args.host,
            port=args.port,
            user=args.admin_user,
            password=admin_password,
            dbname="postgres",
            autocommit=True,
        )
    except psycopg.OperationalError as e:
        print(f"Error connecting as admin: {e}", file=sys.stderr)
        return 1

    role_password = args.role_password
    password_generated_now = False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (args.role,))
            role_exists = cur.fetchone() is not None

            if not role_exists:
                if role_password is None:
                    role_password = _generate_password()
                    password_generated_now = True
                # CREATE ROLE doesn't accept a bind parameter (%s) in the
                # PASSWORD clause — it's DDL, not DML; psycopg3's extended
                # protocol sends "$1" and Postgres rejects it as a syntax
                # error. psycopg.sql builds the already-escaped literal
                # straight into the command text, no bind parameter.
                cur.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                        sql.Identifier(args.role), sql.Literal(role_password)
                    )
                )
                print(f"Role '{args.role}' created.")
            elif args.recreate_password:
                if role_password is None:
                    role_password = _generate_password()
                    password_generated_now = True
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                        sql.Identifier(args.role), sql.Literal(role_password)
                    )
                )
                print(f"Password for role '{args.role}' rotated.")
            else:
                # already existed, no rotation requested — password unknown here
                role_password = None
                print(
                    f"Role '{args.role}' already exists (password unchanged — "
                    "use --recreate-password to rotate)."
                )

            databases = [args.database]
            if not args.no_test_database:
                databases.append(args.test_database)

            for database in databases:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
                if cur.fetchone() is not None:
                    print(f"Database '{database}' already exists.")
                    continue
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(database), sql.Identifier(args.role)
                    )
                )
                print(f"Database '{database}' created (owner: {args.role}).")
    finally:
        conn.close()

    print()
    if role_password:
        print("Connection string (keep it safe — it won't be shown again):")
        print(
            f"  postgresql+psycopg://{args.role}:{role_password}@{args.host}:{args.port}/{args.database}"
        )
        if password_generated_now:
            print("(password auto-generated by this command)")
    else:
        print(
            "The role already existed and its password wasn't changed in this "
            "run — use the password you already have, or re-run with "
            "--recreate-password to rotate it."
        )

    return 0
