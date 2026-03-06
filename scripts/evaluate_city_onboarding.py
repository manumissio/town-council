#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import sessionmaker

from pipeline.models import Catalog, Document, Event, db_connect


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass
class CityMetrics:
    run_count: int
    crawl_success_count: int
    search_success_count: int
    catalog_total: int
    extraction_non_empty_count: int
    segmentation_complete_empty_count: int
    segmentation_failed_count: int


def _parse_iso_utc(value: str) -> datetime:
    dt = datetime.strptime(value, ISO_FMT)
    return dt.replace(tzinfo=timezone.utc)


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _load_city_metadata_slugs() -> set[str]:
    path = Path("city_metadata/list_of_cities.csv")
    slugs: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            division = (row.get("ocd_division_id") or "").strip()
            if "/place:" not in division:
                continue
            slugs.add(division.split("/place:", 1)[1])
    return slugs


def _load_runs(path: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not path.exists():
        return runs
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        row["started_dt"] = _parse_iso_utc(row["started_at_utc"])
        row["finished_dt"] = _parse_iso_utc(row["finished_at_utc"])
        runs.append(row)
    return runs


def _collect_city_metrics(db_session, city: str, city_runs: list[dict[str, Any]]) -> CityMetrics:
    windows = []
    for run in city_runs:
        windows.append((run["started_dt"].replace(tzinfo=None), run["finished_dt"].replace(tzinfo=None)))

    crawl_success_count = sum(1 for run in city_runs if run.get("crawler_status") == "success")
    search_success_count = sum(1 for run in city_runs if run.get("search_status") == "success")

    if not windows:
        return CityMetrics(
            run_count=0,
            crawl_success_count=0,
            search_success_count=0,
            catalog_total=0,
            extraction_non_empty_count=0,
            segmentation_complete_empty_count=0,
            segmentation_failed_count=0,
        )

    window_filters = [
        and_(Event.scraped_datetime >= start_dt, Event.scraped_datetime <= end_dt)
        for start_dt, end_dt in windows
    ]

    event_ids = [
        row[0]
        for row in db_session.query(Event.id)
        .filter(Event.source == city)
        .filter(or_(*window_filters))
        .all()
    ]

    # Delta crawls can succeed without inserting new events in a given run window.
    # Fall back to existing city corpus so extraction/segmentation gates remain evaluable.
    if not event_ids:
        event_ids = [
            row[0]
            for row in db_session.query(Event.id)
            .filter(Event.source == city)
            .all()
        ]

    if not event_ids:
        return CityMetrics(
            run_count=len(city_runs),
            crawl_success_count=crawl_success_count,
            search_success_count=search_success_count,
            catalog_total=0,
            extraction_non_empty_count=0,
            segmentation_complete_empty_count=0,
            segmentation_failed_count=0,
        )

    catalog_rows = (
        db_session.query(Catalog.content, Catalog.agenda_segmentation_status)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Document.event_id.in_(event_ids))
        .all()
    )

    catalog_total = len(catalog_rows)
    extraction_non_empty_count = sum(
        1
        for content, _status in catalog_rows
        if content is not None and str(content).strip() != ""
    )
    segmentation_complete_empty_count = sum(
        1
        for _content, status in catalog_rows
        if status in {"complete", "empty"}
    )
    segmentation_failed_count = sum(1 for _content, status in catalog_rows if status == "failed")

    return CityMetrics(
        run_count=len(city_runs),
        crawl_success_count=crawl_success_count,
        search_success_count=search_success_count,
        catalog_total=catalog_total,
        extraction_non_empty_count=extraction_non_empty_count,
        segmentation_complete_empty_count=segmentation_complete_empty_count,
        segmentation_failed_count=segmentation_failed_count,
    )


def _evaluate_city(city: str, metrics: CityMetrics) -> dict[str, Any]:
    crawl_success_rate = _safe_rate(metrics.crawl_success_count, metrics.run_count)
    extraction_non_empty_rate = _safe_rate(metrics.extraction_non_empty_count, metrics.catalog_total)
    segmentation_complete_empty_rate = _safe_rate(metrics.segmentation_complete_empty_count, metrics.catalog_total)
    segmentation_failed_rate = _safe_rate(metrics.segmentation_failed_count, metrics.catalog_total)

    insufficient_data = metrics.run_count <= 0 or metrics.catalog_total <= 0

    gates = {
        "crawl_success_rate_gte_95pct": bool(crawl_success_rate is not None and crawl_success_rate >= 0.95),
        "non_empty_extraction_rate_gte_90pct": bool(
            extraction_non_empty_rate is not None and extraction_non_empty_rate >= 0.90
        ),
        "segmentation_complete_empty_rate_gte_95pct": bool(
            segmentation_complete_empty_rate is not None and segmentation_complete_empty_rate >= 0.95
        ),
        "segmentation_failed_rate_lt_5pct": bool(
            segmentation_failed_rate is not None and segmentation_failed_rate < 0.05
        ),
        "searchability_smoke_pass": bool(metrics.search_success_count == metrics.run_count and metrics.run_count > 0),
    }

    failed_gates = [name for name, passed in gates.items() if not passed]
    quality_gate = "pass" if (not insufficient_data and not failed_gates) else ("insufficient_data" if insufficient_data else "fail")

    return {
        "city": city,
        "run_count": metrics.run_count,
        "crawl_success_count": metrics.crawl_success_count,
        "search_success_count": metrics.search_success_count,
        "catalog_total": metrics.catalog_total,
        "extraction_non_empty_count": metrics.extraction_non_empty_count,
        "segmentation_complete_empty_count": metrics.segmentation_complete_empty_count,
        "segmentation_failed_count": metrics.segmentation_failed_count,
        "crawl_success_rate": crawl_success_rate,
        "extraction_non_empty_rate": extraction_non_empty_rate,
        "segmentation_complete_empty_rate": segmentation_complete_empty_rate,
        "segmentation_failed_rate": segmentation_failed_rate,
        "gates": gates,
        "failed_gates": failed_gates,
        "quality_gate": quality_gate,
    }


def _write_markdown(path: Path, run_id: str, results: list[dict[str, Any]]) -> None:
    lines = [
        "# City Onboarding Gate Evaluation",
        "",
        f"run_id: `{run_id}`",
        "",
        "| city | quality_gate | crawl_success_rate | extraction_non_empty_rate | segmentation_complete_empty_rate | segmentation_failed_rate | failed_gates |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            "| {city} | {quality_gate} | {crawl_success_rate} | {extraction_non_empty_rate} | {segmentation_complete_empty_rate} | {segmentation_failed_rate} | {failed_gates} |".format(
                city=row["city"],
                quality_gate=row["quality_gate"],
                crawl_success_rate="-" if row["crawl_success_rate"] is None else f"{row['crawl_success_rate']:.3f}",
                extraction_non_empty_rate="-" if row["extraction_non_empty_rate"] is None else f"{row['extraction_non_empty_rate']:.3f}",
                segmentation_complete_empty_rate="-" if row["segmentation_complete_empty_rate"] is None else f"{row['segmentation_complete_empty_rate']:.3f}",
                segmentation_failed_rate="-" if row["segmentation_failed_rate"] is None else f"{row['segmentation_failed_rate']:.3f}",
                failed_gates=", ".join(row["failed_gates"]) if row["failed_gates"] else "-",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate city onboarding quality gates")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--cities", default="")
    parser.add_argument("--output-dir", default="experiments/results/city_onboarding")
    args = parser.parse_args()

    run_dir = Path(args.output_dir) / args.run_id
    runs_path = run_dir / "runs.jsonl"

    rows = _load_runs(runs_path)
    if not rows:
        raise SystemExit(f"No run rows found: {runs_path}")

    valid_city_slugs = _load_city_metadata_slugs()
    requested = [c.strip() for c in args.cities.split(",") if c.strip()]
    if requested:
        unknown = [c for c in requested if c not in valid_city_slugs]
        if unknown:
            raise SystemExit(f"Unknown city slug(s): {', '.join(unknown)}")
        selected_cities = requested
    else:
        selected_cities = sorted({row["city"] for row in rows})

    by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["city"] in selected_cities:
            by_city[row["city"]].append(row)

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        results = []
        for city in selected_cities:
            metrics = _collect_city_metrics(session, city, by_city.get(city, []))
            results.append(_evaluate_city(city, metrics))
    finally:
        session.close()

    output_json = run_dir / "city_gate_eval.json"
    output_md = run_dir / "city_gate_eval.md"

    payload = {"run_id": args.run_id, "results": results}
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_markdown(output_md, args.run_id, results)

    print(f"wrote: {output_json}")
    print(f"wrote: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
