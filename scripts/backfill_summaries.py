#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from pipeline.tasks import run_summary_hydration_backfill


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill summaries for eligible catalogs")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    counts = run_summary_hydration_backfill(force=args.force, limit=args.limit)
    if args.json:
        print(json.dumps(counts, sort_keys=True))
        return 0

    print("Summary Hydration Backfill")
    print("==========================")
    for key, value in counts.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
