"""CLI: python -m relaix execute"""

from __future__ import annotations

import argparse
import time

from relaix.cli._common import add_db_arguments, configure_db


def main_execute(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="relaix execute")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single cycle and exit (cron/Task Scheduler use)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Seconds to sleep between cycles when not using --once (default: 30)",
    )
    add_db_arguments(parser)
    args = parser.parse_args(argv)
    configure_db(args)

    from relaix.executor import dispatch_pending_executions, evaluate_pending_events

    while True:
        evaluated = evaluate_pending_events()
        dispatched = dispatch_pending_executions()
        print(
            f"Evaluated {evaluated['events_processed']} event(s), "
            f"{evaluated['rules_matched']} rule match(es); "
            f"dispatched {dispatched['dispatched']}, "
            f"{dispatched['succeeded']} succeeded."
        )
        if args.once:
            return 0
        time.sleep(args.interval)
