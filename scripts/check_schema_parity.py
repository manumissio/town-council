from __future__ import annotations

import sys

from pipeline.db_migration_alembic import check_database_parity
from pipeline.db_schema_contracts import format_schema_differences
from pipeline.models import db_connect


def main() -> int:
    engine = db_connect()
    try:
        schema_differences = check_database_parity(engine)
    finally:
        engine.dispose()
    if not schema_differences:
        print("Schema parity: PASS")
        return 0
    print(format_schema_differences(schema_differences), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
