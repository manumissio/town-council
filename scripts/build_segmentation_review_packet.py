#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker

from pipeline.models import Catalog, db_connect


def _load_segment_rows(tasks_path: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if str(row.get("phase") or "") != "segment":
            continue
        cid = int(row["catalog_id"])
        rows[cid] = row
    return rows


def _segment_items_text(row: dict[str, Any]) -> str:
    task_result = row.get("task_result") or {}
    items = task_result.get("items") or []
    if not items:
        return "(no segmented agenda items)"
    lines = []
    for idx, item in enumerate(items, start=1):
        title = (item.get("title") or "").strip() or "(untitled)"
        page = item.get("page_number")
        page_suffix = f" [p.{page}]" if page not in (None, "") else ""
        description = (item.get("description") or "").strip()
        body = f"{idx}. {title}{page_suffix}"
        if description:
            body += f"\n   Description: {description}"
        lines.append(body)
    return "\n".join(lines)


def _source_excerpt(text: str, *, max_lines: int = 18, max_chars: int = 1600) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "(source text unavailable)"
    lines = []
    total = 0
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
        if len(lines) >= max_lines:
            break
    excerpt = "\n".join(lines).strip()
    if len(excerpt) < len(cleaned):
        excerpt += "\n...[truncated]"
    return excerpt or "(source text unavailable)"


def _catalog_source_map(catalog_ids: list[int]) -> dict[int, str]:
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        rows = (
            session.query(Catalog.id, Catalog.content)
            .filter(Catalog.id.in_(catalog_ids))
            .all()
        )
        return {int(cid): _source_excerpt(content or "") for cid, content in rows}
    finally:
        session.close()


def build_review_rows(
    *,
    control_rows: dict[int, dict[str, Any]],
    treatment_rows: dict[int, dict[str, Any]],
    source_map: dict[int, str],
    seed: int,
) -> tuple[list[list[str]], list[list[str]]]:
    rng = random.Random(seed)
    blind_rows: list[list[str]] = []
    key_rows: list[list[str]] = []

    for idx, catalog_id in enumerate(sorted(source_map), start=1):
        control = control_rows[catalog_id]
        treatment = treatment_rows[catalog_id]
        sample_id = f"S{idx:03d}"
        if rng.random() < 0.5:
            option_a, option_b = control, treatment
            arm_a, arm_b = "A", "B"
        else:
            option_a, option_b = treatment, control
            arm_a, arm_b = "B", "A"

        blind_rows.append(
            [
                sample_id,
                str(catalog_id),
                source_map[catalog_id],
                _segment_items_text(option_a),
                _segment_items_text(option_b),
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
        key_rows.append([sample_id, str(catalog_id), arm_a, arm_b])
    return blind_rows, key_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a blinded segmentation review packet for A/B arms.")
    parser.add_argument("--control-run", required=True)
    parser.add_argument("--treatment-run", required=True)
    parser.add_argument("--results-root", default="experiments/results")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_root = Path(args.results_root)
    control_tasks = results_root / args.control_run / "tasks.jsonl"
    treatment_tasks = results_root / args.treatment_run / "tasks.jsonl"
    if not control_tasks.exists():
        raise SystemExit(f"missing control tasks file: {control_tasks}")
    if not treatment_tasks.exists():
        raise SystemExit(f"missing treatment tasks file: {treatment_tasks}")

    control_rows = _load_segment_rows(control_tasks)
    treatment_rows = _load_segment_rows(treatment_tasks)
    catalog_ids = sorted(set(control_rows) & set(treatment_rows))
    if not catalog_ids:
        raise SystemExit("no paired segment rows found")

    source_map = _catalog_source_map(catalog_ids)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    blind_rows, key_rows = build_review_rows(
        control_rows=control_rows,
        treatment_rows=treatment_rows,
        source_map=source_map,
        seed=args.seed,
    )

    blind_path = output_dir / "segmentation_review_blind_v1.csv"
    key_path = output_dir / "segmentation_review_key_v1.csv"
    manifest_path = output_dir / "segmentation_review_manifest.json"

    with blind_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "sample_id",
                "catalog_id",
                "source_excerpt",
                "option_a_segmented_items",
                "option_b_segmented_items",
                "better_overall_option",
                "major_items_missing_in_a",
                "major_items_missing_in_b",
                "obvious_boilerplate_in_a",
                "obvious_boilerplate_in_b",
                "notes",
            ]
        )
        writer.writerows(blind_rows)

    with key_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_id", "catalog_id", "option_a_arm", "option_b_arm"])
        writer.writerows(key_rows)

    manifest_path.write_text(
        json.dumps(
            {
                "control_run": args.control_run,
                "treatment_run": args.treatment_run,
                "catalog_ids": catalog_ids,
                "seed": args.seed,
                "blind_csv": str(blind_path),
                "key_csv": str(key_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"wrote blind sheet: {blind_path}")
    print(f"wrote key sheet: {key_path}")
    print(f"wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
