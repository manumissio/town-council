#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid


def parse_launch_response(raw: str) -> dict[str, object]:
    try:
        obj = json.loads(raw) if raw else {}
    except Exception:
        obj = {}

    if not isinstance(obj, dict):
        obj = {}

    task_id = str(obj.get("task_id") or "").strip()
    status = str(obj.get("status") or "").strip()
    detail = str(obj.get("detail") or "").strip()

    task_id_valid = False
    if task_id:
        try:
            uuid.UUID(task_id)
        except Exception:
            task_id_valid = False
        else:
            task_id_valid = True

    return {
        "task_id": task_id if task_id_valid else "",
        "task_id_valid": task_id_valid,
        "status": status,
        "detail": detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse soak task launch response safely")
    parser.add_argument("--raw", default="")
    parser.add_argument("--field", choices=["task_id", "task_id_valid", "status", "detail"], default=None)
    args = parser.parse_args()

    parsed = parse_launch_response(args.raw)
    if args.field is not None:
        value = parsed[args.field]
        if isinstance(value, bool):
            print("true" if value else "false")
        else:
            print(value)
        return 0

    print(json.dumps(parsed, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
