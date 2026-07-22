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

    from relaix.collector import poll_all_active_sources

    while True:
        results = poll_all_active_sources()
        new_total = sum(r["new_events_found"] for r in results)
        print(f"Polled {len(results)} source(s), {new_total} new event(s).")
        if args.once:
            return 0
        time.sleep(args.interval)
