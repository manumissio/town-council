#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text

from pipeline.models import db_connect


QUERY = """
SELECT
  datname,
  datcollversion,
  pg_database_collation_actual_version(oid) AS actual_collversion
FROM pg_database
WHERE datname = current_database()
"""


def _collation_state() -> dict[str, str | bool | None]:
    engine = db_connect()
    with engine.connect() as conn:
        row = conn.execute(text(QUERY)).mappings().one()
    expected = row["datcollversion"]
    actual = row["actual_collversion"]
    return {
        "database": row["datname"],
        "expected_collversion": expected,
        "actual_collversion": actual,
        "matches": expected == actual,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PostgreSQL collation-version drift for the current database.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text.")
    args = parser.parse_args()

    state = _collation_state()
    if args.json:
        print(json.dumps(state))
    else:
        print(
            "database={database} expected_collversion={expected_collversion} "
            "actual_collversion={actual_collversion} matches={matches}".format(**state)
        )
        if not state["matches"]:
            print(
                "remediation: rebuild collation-sensitive objects first, then run "
                "'ALTER DATABASE {database} REFRESH COLLATION VERSION;'".format(**state),
                file=sys.stderr,
            )
    return 0 if state["matches"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
