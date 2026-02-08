"""
CLI: run Agenda QA scoring over the database and write a report.

Default mode is report-only (safe). Regeneration is opt-in via --regenerate.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import sessionmaker

from pipeline.agenda_qa import QAThresholds, needs_regeneration, score_agenda_items
from pipeline.models import db_connect, Catalog, AgendaItem


def _default_out_dir() -> str:
    data_dir = os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data"))
    return os.path.join(data_dir, "reports")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _city_for_catalog(catalog: Catalog) -> Optional[str]:
    """
    Best-effort city label for reporting. Not all catalogs are linked.
    """
    try:
        doc = catalog.document
        if not doc or not doc.place:
            return None
        return doc.place.display_name or doc.place.name
    except Exception:
        return None


def _meeting_date_for_catalog(catalog: Catalog) -> Optional[str]:
    try:
        doc = catalog.document
        if doc and doc.event and doc.event.record_date:
            return doc.event.record_date.isoformat()
        return None
    except Exception:
        return None


def _iter_catalogs(session, *, limit: Optional[int] = None) -> Iterable[Catalog]:
    q = session.query(Catalog).order_by(Catalog.id.asc())
    if limit is not None:
        q = q.limit(limit)
    return q.yield_per(250)


def _summarize(results: List[Dict]) -> Dict:
    by_city: Dict[str, Dict] = {}
    flagged = [r for r in results if r.get("needs_regeneration")]

    for r in results:
        city = r.get("city") or "unknown"
        bucket = by_city.setdefault(
            city,
            {
                "catalog_count": 0,
                "flagged_count": 0,
                "avg_severity": 0.0,
                "vote_failures": 0,
                "page_failures": 0,
            },
        )
        bucket["catalog_count"] += 1
        bucket["avg_severity"] += float(r.get("severity", 0))
        if r.get("needs_regeneration"):
            bucket["flagged_count"] += 1
        flags = set(r.get("flags") or [])
        if "votes_missed" in flags:
            bucket["vote_failures"] += 1
        if "page_numbers_suspect" in flags:
            bucket["page_failures"] += 1

    for bucket in by_city.values():
        if bucket["catalog_count"]:
            bucket["avg_severity"] = round(bucket["avg_severity"] / bucket["catalog_count"], 2)

    worst_overall = sorted(results, key=lambda r: (r.get("severity", 0), r.get("catalog_id", 0)), reverse=True)[:50]
    worst_flagged = sorted(flagged, key=lambda r: (r.get("severity", 0), r.get("catalog_id", 0)), reverse=True)[:50]

    vote_failures = [r for r in results if "votes_missed" in (r.get("flags") or [])]
    page_failures = [r for r in results if "page_numbers_suspect" in (r.get("flags") or [])]

    return {
        "catalog_count": len(results),
        "flagged_count": len(flagged),
        "by_city": by_city,
        "worst_overall": worst_overall,
        "worst_flagged": worst_flagged,
        "vote_failures": sorted(vote_failures, key=lambda r: r.get("catalog_id", 0))[:50],
        "page_failures": sorted(page_failures, key=lambda r: r.get("catalog_id", 0))[:50],
    }


def _write_json(path: str, payload: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def _write_csv(path: str, rows: List[Dict]) -> None:
    fieldnames = [
        "catalog_id",
        "city",
        "meeting_date",
        "severity",
        "needs_regeneration",
        "flags",
        "item_count",
        "boilerplate_rate",
        "name_like_rate",
        "page_one_rate",
        "missing_page_count",
        "raw_vote_lines",
        "extracted_vote_count",
        "max_page_in_raw",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            metrics = r.get("metrics") or {}
            w.writerow(
                {
                    "catalog_id": r.get("catalog_id"),
                    "city": r.get("city"),
                    "meeting_date": r.get("meeting_date"),
                    "severity": r.get("severity"),
                    "needs_regeneration": r.get("needs_regeneration"),
                    "flags": ";".join(r.get("flags") or []),
                    "item_count": metrics.get("item_count"),
                    "boilerplate_rate": metrics.get("boilerplate_rate"),
                    "name_like_rate": metrics.get("name_like_rate"),
                    "page_one_rate": metrics.get("page_one_rate"),
                    "missing_page_count": metrics.get("missing_page_count"),
                    "raw_vote_lines": metrics.get("raw_vote_lines"),
                    "extracted_vote_count": metrics.get("extracted_vote_count"),
                    "max_page_in_raw": metrics.get("max_page_in_raw"),
                }
            )


def _configure_celery_env() -> None:
    """
    Regeneration uses Celery tasks. The pipeline container doesn't always export
    the broker URLs, so we set safe defaults that match docker-compose.yml.
    """
    if os.getenv("CELERY_BROKER_URL") and os.getenv("CELERY_RESULT_BACKEND"):
        return

    redis_password = os.getenv("REDIS_PASSWORD", "secure_redis_password")
    default_url = f"redis://:{redis_password}@redis:6379/0"
    os.environ.setdefault("CELERY_BROKER_URL", default_url)
    os.environ.setdefault("CELERY_RESULT_BACKEND", default_url)


def _enqueue_regeneration(catalog_ids: List[int], *, sleep_s: float, max_count: int) -> List[Dict]:
    """
    Enqueue segmentation for catalog_ids. Returns task records for reporting.
    """
    import time

    _configure_celery_env()
    # Import only when needed to keep report-only runs lightweight.
    from pipeline.tasks import segment_agenda_task

    queued: List[Dict] = []
    for i, catalog_id in enumerate(catalog_ids[:max_count]):
        task = segment_agenda_task.delay(int(catalog_id))
        queued.append({"catalog_id": int(catalog_id), "task_id": str(task.id)})
        if sleep_s > 0 and i < (min(max_count, len(catalog_ids)) - 1):
            time.sleep(sleep_s)
    return queued


def main() -> int:
    p = argparse.ArgumentParser(description="Run Agenda QA scoring and write a report.")
    p.add_argument("--limit", type=int, default=None, help="Limit number of catalogs to scan (for quick smoke tests).")
    p.add_argument("--out-dir", type=str, default=_default_out_dir(), help="Output directory for reports.")
    p.add_argument("--regenerate", action="store_true", help="Enqueue regeneration for catalogs that look low quality.")
    p.add_argument("--max", type=int, default=50, help="Max number of catalogs to regenerate when --regenerate is set.")
    p.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between enqueued tasks.")
    args = p.parse_args()

    engine = db_connect()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    thresholds = QAThresholds()
    results: List[Dict] = []

    session = SessionLocal()
    try:
        for catalog in _iter_catalogs(session, limit=args.limit):
            items = (
                session.query(AgendaItem)
                .filter(AgendaItem.catalog_id == catalog.id)
                .order_by(AgendaItem.order.asc())
                .all()
            )

            result = score_agenda_items(
                items,
                catalog.content or "",
                thresholds=thresholds,
                catalog_id=catalog.id,
                city=_city_for_catalog(catalog),
                meeting_date=_meeting_date_for_catalog(catalog),
            )
            row = result.to_dict()
            row["needs_regeneration"] = needs_regeneration(result, thresholds=thresholds)
            results.append(row)

    finally:
        session.close()

    _ensure_dir(args.out_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(args.out_dir, f"agenda_qa_{ts}.json")
    csv_path = os.path.join(args.out_dir, f"agenda_qa_{ts}.csv")

    payload = {
        "generated_at": ts,
        "thresholds": {
            "suspect_boilerplate_rate": thresholds.suspect_boilerplate_rate,
            "suspect_name_rate": thresholds.suspect_name_rate,
            "suspect_item_count_high": thresholds.suspect_item_count_high,
            "suspect_page_one_rate": thresholds.suspect_page_one_rate,
            "suspect_severity": thresholds.suspect_severity,
        },
        "summary": _summarize(results),
        # Keep the per-catalog rows lightweight (no raw text).
        "rows": results,
    }

    queued = []
    if args.regenerate:
        flagged = [r for r in results if r.get("needs_regeneration")]
        flagged_ids = [int(r["catalog_id"]) for r in flagged if r.get("catalog_id") is not None]
        queued = _enqueue_regeneration(flagged_ids, sleep_s=float(args.sleep), max_count=int(args.max))
        payload["regeneration"] = {"queued_count": len(queued), "queued": queued}

    _write_json(json_path, payload)
    _write_csv(csv_path, results)

    print(f"Wrote report: {json_path}")
    print(f"Wrote report: {csv_path}")
    if args.regenerate:
        print(f"Queued regenerations: {len(queued)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

