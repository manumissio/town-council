#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from pipeline.agenda_worker import run_agenda_segmentation_backfill


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill agenda segmentation for eligible catalogs")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    counts = run_agenda_segmentation_backfill(limit=args.limit)
    if args.json:
        print(json.dumps(counts, sort_keys=True))
        return 0

    print("Agenda Segmentation Backfill")
    print("===========================")
    for key, value in counts.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
