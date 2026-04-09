from __future__ import annotations

from typing import Any

from sqlalchemy import text

from pipeline.config import LINEAGE_MIN_EDGE_CONFIDENCE, LINEAGE_REQUIRE_MUTUAL_EDGES
from pipeline.lineage_service import compute_lineage_assignments
from pipeline.metrics import record_lineage_recompute


LINEAGE_RECOMPUTE_LOCK_KEY = 90412031


def run_lineage_recompute(db) -> dict[str, Any]:
    """
    Full lineage recompute stays centralized so task wrappers only own retry boundaries.
    """
    lock_acquired = False
    try:
        is_postgres = db.get_bind().dialect.name == "postgresql"
        if is_postgres:
            row = db.execute(
                text("SELECT pg_try_advisory_lock(:k)"),
                {"k": LINEAGE_RECOMPUTE_LOCK_KEY},
            ).first()
            lock_acquired = bool(row and row[0])
            if not lock_acquired:
                return {"status": "skipped", "reason": "lineage_recompute_in_progress"}

        # Full recompute is intentional: one new bridge edge can merge multiple prior components.
        result = compute_lineage_assignments(
            db,
            min_edge_confidence=LINEAGE_MIN_EDGE_CONFIDENCE,
            require_mutual_edges=LINEAGE_REQUIRE_MUTUAL_EDGES,
        )
        db.commit()
        record_lineage_recompute(
            updated_count=result.updated_count,
            merge_count=result.merge_count,
        )
        return {
            "status": "complete",
            "catalog_count": result.catalog_count,
            "component_count": result.component_count,
            "merge_count": result.merge_count,
            "updated_count": result.updated_count,
        }
    finally:
        if lock_acquired:
            try:
                db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LINEAGE_RECOMPUTE_LOCK_KEY})
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
