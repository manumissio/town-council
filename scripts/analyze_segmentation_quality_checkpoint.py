#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker

from pipeline.agenda_qa import score_agenda_items
from pipeline.models import Catalog, db_connect


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _segment_rows_by_catalog(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("phase") or "") != "segment":
            continue
        out[int(row["catalog_id"])] = row
    return out


def _gating_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("phase") or "") in {"segment", "summarize"}]


def _catalog_text_map(catalog_ids: list[int]) -> dict[int, str]:
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        pairs = (
            session.query(Catalog.id, Catalog.content)
            .filter(Catalog.id.in_(catalog_ids))
            .all()
        )
        return {int(cid): (content or "") for cid, content in pairs}
    finally:
        session.close()


def _qa_for_row(row: dict[str, Any], catalog_text: str) -> dict[str, Any]:
    task_result = row.get("task_result") or {}
    items = task_result.get("items") or []
    result = score_agenda_items(
        items,
        catalog_text,
        catalog_id=int(row["catalog_id"]),
    )
    payload = result.to_dict()
    payload["item_count"] = int(task_result.get("item_count") or len(items))
    return payload


def _manual_review_summary(blind_csv: Path, key_csv: Path) -> dict[str, Any]:
    blind_rows = {}
    with blind_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            blind_rows[row["sample_id"]] = row

    key_rows = {}
    with key_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key_rows[row["sample_id"]] = row

    treatment_failures = []
    for sample_id, mapping in key_rows.items():
        blind = blind_rows.get(sample_id, {})
        option_a_arm = (mapping.get("option_a_arm") or "").strip().upper()
        option_b_arm = (mapping.get("option_b_arm") or "").strip().upper()

        missing_a = (blind.get("major_items_missing_in_a") or "").strip()
        missing_b = (blind.get("major_items_missing_in_b") or "").strip()
        boilerplate_a = (blind.get("obvious_boilerplate_in_a") or "").strip()
        boilerplate_b = (blind.get("obvious_boilerplate_in_b") or "").strip()

        if option_a_arm == "B" and missing_a:
            treatment_failures.append({"sample_id": sample_id, "catalog_id": mapping.get("catalog_id"), "type": "major_items_missing", "details": missing_a})
        if option_b_arm == "B" and missing_b:
            treatment_failures.append({"sample_id": sample_id, "catalog_id": mapping.get("catalog_id"), "type": "major_items_missing", "details": missing_b})
        if option_a_arm == "B" and boilerplate_a:
            treatment_failures.append({"sample_id": sample_id, "catalog_id": mapping.get("catalog_id"), "type": "boilerplate", "details": boilerplate_a})
        if option_b_arm == "B" and boilerplate_b:
            treatment_failures.append({"sample_id": sample_id, "catalog_id": mapping.get("catalog_id"), "type": "boilerplate", "details": boilerplate_b})

    return {
        "treatment_failures": treatment_failures,
        "treatment_passes": len(treatment_failures) == 0,
    }


def _gating_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = []
    for row in _gating_rows(rows):
        phase = str(row.get("phase") or "")
        task_failed = bool(row.get("task_failed"))
        status = str(row.get("status") or "")
        task_result = row.get("task_result") or {}
        summary_text = str(task_result.get("summary") or "").lower()
        if task_failed or status == "failed":
            failures.append({"catalog_id": row["catalog_id"], "phase": phase, "reason": "task_failed"})
        if phase == "summarize" and ("agenda summary unavailable" in summary_text or "no substantive actions were retained after filtering" in summary_text):
            failures.append({"catalog_id": row["catalog_id"], "phase": phase, "reason": "fallback_detected"})
    return {"failures": failures, "passes": len(failures) == 0}


def _per_catalog_report(control_segments: dict[int, dict[str, Any]], treatment_segments: dict[int, dict[str, Any]], catalog_text: dict[int, str]) -> list[dict[str, Any]]:
    reports = []
    for cid in sorted(set(control_segments) & set(treatment_segments)):
        control_qa = _qa_for_row(control_segments[cid], catalog_text.get(cid, ""))
        treatment_qa = _qa_for_row(treatment_segments[cid], catalog_text.get(cid, ""))
        control_count = int(control_qa["item_count"])
        treatment_count = int(treatment_qa["item_count"])
        count_drop_pct = 0.0
        if control_count > 0:
            count_drop_pct = ((control_count - treatment_count) / control_count) * 100.0
        reports.append(
            {
                "catalog_id": cid,
                "control": {
                    "item_count": control_count,
                    "severity": int(control_qa["severity"]),
                    "flags": control_qa["flags"],
                },
                "treatment": {
                    "item_count": treatment_count,
                    "severity": int(treatment_qa["severity"]),
                    "flags": treatment_qa["flags"],
                },
                "severity_delta": int(treatment_qa["severity"]) - int(control_qa["severity"]),
                "item_count_drop_pct": round(count_drop_pct, 2),
                "item_count_guardrail_pass": count_drop_pct <= 50.0,
                "severity_guardrail_pass": (int(treatment_qa["severity"]) - int(control_qa["severity"])) <= 10,
            }
        )
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze the host-Metal Gemma 4 segmentation quality checkpoint.")
    parser.add_argument("--control-run", required=True)
    parser.add_argument("--treatment-run", required=True)
    parser.add_argument("--results-root", default="experiments/results")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--review-csv")
    parser.add_argument("--review-key-csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.results_root)
    control_rows = _load_tasks(root / args.control_run / "tasks.jsonl")
    treatment_rows = _load_tasks(root / args.treatment_run / "tasks.jsonl")
    control_segments = _segment_rows_by_catalog(control_rows)
    treatment_segments = _segment_rows_by_catalog(treatment_rows)
    catalog_ids = sorted(set(control_segments) & set(treatment_segments))
    if not catalog_ids:
        raise SystemExit("no paired segment rows found")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_text = _catalog_text_map(catalog_ids)

    per_catalog = _per_catalog_report(control_segments, treatment_segments, catalog_text)
    gating = {
        "control": _gating_summary(control_rows),
        "treatment": _gating_summary(treatment_rows),
    }

    manual = None
    if args.review_csv and args.review_key_csv:
        manual = _manual_review_summary(Path(args.review_csv), Path(args.review_key_csv))

    payload = {
        "control_run": args.control_run,
        "treatment_run": args.treatment_run,
        "catalog_ids": catalog_ids,
        "gating": gating,
        "per_catalog": per_catalog,
        "manual_review": manual,
    }
    out_path = output_dir / "segmentation_quality_checkpoint_report.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
