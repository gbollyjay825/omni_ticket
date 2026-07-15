from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence

from app.core.store import store
from app.db.bootstrap import initialize_database
from app.db.session import SessionLocal
from app.services.worker import worker_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Omni Ticket background jobs.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one worker cycle and exit.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Delay between worker cycles when --once is not supplied.",
    )
    parser.add_argument(
        "--market-id",
        action="append",
        dest="market_ids",
        help="Limit the worker to one market. Can be passed more than once.",
    )
    parser.add_argument(
        "--outbound-limit",
        type=int,
        default=50,
        help="Maximum due outbound messages to process per market per cycle.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from app.core.config import settings

    settings.validate_for_process("worker")
    initialize_database()
    while True:
        with SessionLocal() as db:
            summary = worker_service.run_once(
                db,
                store,
                market_ids=args.market_ids,
                outbound_limit=args.outbound_limit or settings.worker_outbound_limit,
            )
        print(json.dumps(summary.to_dict(), indent=2, sort_keys=True), flush=True)
        if args.once:
            return 0
        time.sleep(max(args.interval_seconds, 1))


if __name__ == "__main__":
    raise SystemExit(main())
