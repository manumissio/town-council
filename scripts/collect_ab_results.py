#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from pipeline.models import db_connect, Catalog, Document, AgendaItem
from pipeline.summary_quality import is_summary_grounded

REQUIRED_SECTIONS = [
    "bluf:",
    "why this matters:",
    "top actions:",
    "potential impacts:",
    "unknowns:",
]


def _section_compliance(summary: str) -> bool:
    text = (summary or "").lower()
    return all(marker in text for marker in REQUIRED_SECTIONS)


def _detect_fallback(summary: str) -> bool:
    text = (summary or "").lower()
    return (
        "no substantive actions were retained after filtering" in text
        or "agenda summary unavailable" in text
    )


def _detect_partial_coverage(summary: str) -> bool:
    text = (summary or "").lower()
    patterns = [
        r"partial coverage",
        r"included\s+\d+\s+of\s+\d+\s+items",
        r"first\s+\d+\s+of\s+\d+",
    ]
    return any(re.search(p, text) for p in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect A/B run results into CSV/JSON artifacts")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", default="experiments/results")
    args = parser.parse_args()

    run_dir = Path(args.results_root) / args.run_id
    tasks_path = run_dir / "tasks.jsonl"
    if not tasks_path.exists():
        raise SystemExit(f"missing tasks file: {tasks_path}")

    by_cid_phase = {}
    arm = None
    with tasks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cid = int(row["catalog_id"])
            phase = str(row.get("phase") or "")
            by_cid_phase[(cid, phase)] = row
            arm = arm or row.get("arm")

    cids = sorted({cid for cid, _ in by_cid_phase.keys()})

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    db = Session()

    out_rows = []
    try:
        for cid in cids:
            catalog = db.get(Catalog, cid)
            if catalog is None:
                continue
            doc = db.query(Document).filter(Document.catalog_id == cid).first()
            doc_kind = (doc.category or "unknown") if doc else "unknown"
            items = (
                db.query(AgendaItem)
                .filter(AgendaItem.catalog_id == cid)
                .order_by(AgendaItem.order)
                .all()
            )
            agenda_items_count = len(items)

            summary_text = (catalog.summary or "").strip()
            if doc_kind == "agenda":
                source = "\n".join(
                    " | ".join(
                        [
                            (it.title or "").strip(),
                            (it.description or "").strip(),
                            (it.classification or "").strip(),
                            (it.result or "").strip(),
                        ]
                    ).strip(" | ")
                    for it in items
                )
            else:
                source = (catalog.content or "")

            grounding = is_summary_grounded(summary_text, source or "")

            seg = by_cid_phase.get((cid, "segment"), {})
            summ = by_cid_phase.get((cid, "summarize"), {})

            any_failed = bool(seg.get("task_failed")) or bool(summ.get("task_failed"))
            status = "failed" if any_failed else "complete"

            out_rows.append(
                {
                    "run_id": args.run_id,
                    "arm": arm or "",
                    "catalog_id": cid,
                    "doc_kind": doc_kind,
                    "status": status,
                    "segment_duration_s": float(seg.get("duration_s") or 0.0),
                    "summary_duration_s": float(summ.get("duration_s") or 0.0),
                    "task_failed": any_failed,
                    "agenda_items_count": agenda_items_count,
                    "summary_chars": len(summary_text),
                    "summary_text": summary_text,
                    "section_compliance_pass": _section_compliance(summary_text),
                    "grounding_pass": bool(grounding.is_grounded),
                    "fallback_used": _detect_fallback(summary_text),
                    "partial_coverage_disclosed": _detect_partial_coverage(summary_text),
                }
            )
    finally:
        db.close()

    csv_path = run_dir / "ab_rows.csv"
    json_path = run_dir / "ab_rows.json"
    fieldnames = [
        "run_id",
        "arm",
        "catalog_id",
        "doc_kind",
        "status",
        "segment_duration_s",
        "summary_duration_s",
        "task_failed",
        "agenda_items_count",
        "summary_chars",
        "summary_text",
        "section_compliance_pass",
        "grounding_pass",
        "fallback_used",
        "partial_coverage_disclosed",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(out_rows, f, indent=2)

    print(f"wrote {len(out_rows)} rows to {csv_path} and {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
