"""CLI: python -m relaix collect"""

from __future__ import annotations

import argparse
import time

from relaix.cli._common import add_db_arguments, configure_db


def main_collect(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="relaix collect")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single cycle and exit (cron/Task Scheduler use)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Seconds to sleep between cycles when not using --once (default: 60)",
    )
    add_db_arguments(parser)
    args = parser.parse_args(argv)
    configure_db(args)

    from conta_tools_shared.status import StatusFile
    from relaix.collector import poll_all_active_sources
    from relaix.status_paths import CAMINHO_COLLECT

    status_file = StatusFile(CAMINHO_COLLECT)

    while True:
        try:
            results = poll_all_active_sources()
            new_total = sum(r["new_events_found"] for r in results)
            print(f"Polled {len(results)} source(s), {new_total} new event(s).")
            status_file.registrar(ok=True, counters={"sources": len(results), "new_events": new_total})
        except Exception as exc:
            status_file.registrar(ok=False, erro=str(exc))
            raise
        if args.once:
            return 0
        time.sleep(args.interval)
