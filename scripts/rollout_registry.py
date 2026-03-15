#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.rollout_registry import (
    ROLLOUT_REGISTRY_PATH,
    load_rollout_entry,
    load_rollout_registry,
    load_wave_city_slugs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read and validate city rollout registry metadata.")
    parser.add_argument("--wave", help="Print newline-delimited city slugs for the requested wave.")
    parser.add_argument("--validate", action="store_true", help="Validate the registry and print a short summary.")
    parser.add_argument("--city", help="Lookup a specific city in the rollout registry.")
    parser.add_argument("--field", help="Print a single field value for --city.")
    args = parser.parse_args()

    if not args.wave and not args.validate and not args.city:
        parser.error("one of --wave, --validate, or --city is required")

    if args.validate:
        entries = load_rollout_registry()
        print(f"validated {len(entries)} rollout entries from {ROLLOUT_REGISTRY_PATH}")

    if args.wave:
        for city_slug in load_wave_city_slugs(args.wave):
            print(city_slug)

    if args.city:
        entry = load_rollout_entry(args.city)
        if args.field:
            print(getattr(entry, args.field))
        else:
            print(entry)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
