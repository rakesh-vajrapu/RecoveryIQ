from __future__ import annotations

import argparse
import json

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.demo_cases import (
    DemoResetBlockedError,
    DemoSeedDisabledError,
    reset_demo_cases,
    seed_demo_cases,
)

_BANNER = "\n".join(
    (
        "DEMO SYNTHETIC DATASET",
        "NOT RAZORPAY TRANSACTIONS",
        "NOT PROVIDER-VERIFIED RECOVERY",
    )
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage local presentation-only demo cases")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove only DEMO_SYNTHETIC records; does not reseed",
    )
    args = parser.parse_args()
    settings = get_settings()
    print(_BANNER)
    output: dict[str, str | int]
    try:
        with SessionLocal.begin() as session:
            if args.reset:
                reset_result = reset_demo_cases(session, settings=settings)
                output = {"operation": "reset", "removed_cases": reset_result.removed_cases}
            else:
                seed_result = seed_demo_cases(session, settings=settings)
                output = {
                    "operation": "seed",
                    "created": seed_result.created,
                    "existing": seed_result.existing,
                    "total_amount_minor": seed_result.total_amount_minor,
                }
    except (DemoSeedDisabledError, DemoResetBlockedError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
