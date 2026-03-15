#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from pipeline.rollout_registry import CITY_SLUG_RE, load_rollout_entry
from scripts.reset_city_verification_state import reset_city_verification_state


def _validate_city_is_rewindable(city: str) -> None:
    if not CITY_SLUG_RE.match(city):
        raise ValueError(f"invalid city slug: {city}")

    entry = load_rollout_entry(city)
    if entry.enabled != "no":
        raise ValueError(f"rewind is only allowed for disabled cities: {city}")
    if entry.quality_gate not in {"pending", "fail"}:
        raise ValueError(f"rewind is only allowed for pending/failing cities: {city}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rewind pending-city onboarding state to a pre-campaign baseline."
    )
    parser.add_argument("--city", required=True)
    parser.add_argument("--since", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the rewind. Without this flag the command is dry-run only.",
    )
    args = parser.parse_args()

    _validate_city_is_rewindable(args.city)
    result = reset_city_verification_state(args.city, args.since, dry_run=not args.apply)
    result["mode"] = "apply" if args.apply else "dry_run"
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
