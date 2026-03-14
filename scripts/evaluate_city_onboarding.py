#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import sessionmaker

from pipeline.models import Catalog, Document, Event, UrlStage, UrlStageHist, db_connect


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
logger = logging.getLogger("city_onboarding_eval")


@dataclass
class CityMetrics:
    run_count: int
    crawl_success_count: int
    search_success_count: int
    catalog_total: int
    agenda_catalog_total: int
    extraction_non_empty_count: int
    segmentation_complete_empty_count: int
    segmentation_failed_count: int
    run_window_catalog_total: int
    run_window_agenda_catalog_total: int
    run_window_extraction_non_empty_count: int
    run_window_segmentation_complete_empty_count: int
    run_window_segmentation_failed_count: int


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


def _source_aliases_for_city(city: str) -> set[str]:
    aliases = {city}
    legacy_aliases = {
        "san_mateo": {"san mateo"},
        "san_leandro": {"san leandro"},
        "mtn_view": {"mountain view"},
    }
    aliases.update(legacy_aliases.get(city, set()))
    return aliases


def _ocd_division_id_for_city(city: str) -> str:
    return f"ocd-division/country:us/state:ca/place:{city}"


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


def _collect_historical_city_catalog_rows(
    db_session, city: str, city_runs: list[dict[str, Any]]
) -> list[tuple[int, str, str | None, str | None]]:
    windows = []
    for run in city_runs:
        windows.append((run["started_dt"].replace(tzinfo=None), run["finished_dt"].replace(tzinfo=None)))
    source_aliases = sorted(_source_aliases_for_city(city))
    if not windows:
        return []

    window_filters = [
        and_(Event.scraped_datetime >= start_dt, Event.scraped_datetime <= end_dt)
        for start_dt, end_dt in windows
    ]

    event_ids = [
        row[0]
        for row in db_session.query(Event.id)
        .filter(Event.source.in_(source_aliases))
        .filter(or_(*window_filters))
        .all()
    ]

    # Delta crawls can succeed without inserting new events in a given run window.
    # Fall back to existing city corpus so extraction/segmentation gates remain evaluable.
    if not event_ids:
        event_ids = [
            row[0]
            for row in db_session.query(Event.id)
            .filter(Event.source.in_(source_aliases))
            .all()
        ]

    if not event_ids:
        return []

    return (
        db_session.query(Catalog.id, Document.category, Catalog.content, Catalog.agenda_segmentation_status)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Document.event_id.in_(event_ids))
        .all()
    )


def _collect_run_window_catalog_rows(
    db_session, city: str, city_runs: list[dict[str, Any]]
) -> tuple[list[tuple[int, str, str | None, str | None]], int]:
    ocd_division_id = _ocd_division_id_for_city(city)

    touched_queries = []
    for run in city_runs:
        started_dt = run["started_dt"].replace(tzinfo=None)
        finished_dt = run["finished_dt"].replace(tzinfo=None)
        touched_queries.append(
            db_session.query(
                UrlStageHist.url_hash.label("url_hash"),
                UrlStageHist.category.label("category"),
            ).filter(
                UrlStageHist.ocd_division_id == ocd_division_id,
                UrlStageHist.created_at >= started_dt,
                UrlStageHist.created_at <= finished_dt,
            )
        )
        touched_queries.append(
            db_session.query(
                UrlStage.url_hash.label("url_hash"),
                UrlStage.category.label("category"),
            ).filter(
                UrlStage.ocd_division_id == ocd_division_id,
                UrlStage.created_at >= started_dt,
                UrlStage.created_at <= finished_dt,
            )
        )

    if not touched_queries:
        return [], 0

    touched_hashes = touched_queries[0]
    for query in touched_queries[1:]:
        touched_hashes = touched_hashes.union(query)

    touched_hashes = touched_hashes.subquery()
    touched_hash_count = db_session.query(touched_hashes.c.url_hash).distinct().count()
    catalog_rows = (
        db_session.query(
            Catalog.id,
            touched_hashes.c.category,
            Catalog.content,
            Catalog.agenda_segmentation_status,
        )
        .join(Catalog, Catalog.url_hash == touched_hashes.c.url_hash)
        .distinct()
        .all()
    )
    logger.info(
        "run_window_scope city=%s ocd_division_id=%s touched_hashes=%s resolved_catalogs=%s source=url_stage_hist+url_stage",
        city,
        ocd_division_id,
        touched_hash_count,
        len(catalog_rows),
    )
    return catalog_rows, touched_hash_count


def _build_counts(catalog_rows: list[tuple[int, str, str | None, str | None]]) -> dict[str, int]:
    return {
        "catalog_total": len(catalog_rows),
        "agenda_catalog_total": sum(1 for _id, category, _content, _status in catalog_rows if category == "agenda"),
        "extraction_non_empty_count": sum(
            1
            for _id, _category, content, _status in catalog_rows
            if content is not None and str(content).strip() != ""
        ),
        "segmentation_complete_empty_count": sum(
            1
            for _id, category, _content, status in catalog_rows
            if category == "agenda" and status in {"complete", "empty"}
        ),
        "segmentation_failed_count": sum(
            1 for _id, category, _content, status in catalog_rows if category == "agenda" and status == "failed"
        ),
    }


def _collect_city_metrics(db_session, city: str, city_runs: list[dict[str, Any]]) -> CityMetrics:
    crawl_success_count = sum(1 for run in city_runs if run.get("crawler_status") == "success")
    search_success_count = sum(1 for run in city_runs if run.get("search_status") == "success")

    historical_counts = _build_counts(_collect_historical_city_catalog_rows(db_session, city, city_runs))
    run_window_rows, touched_hash_count = _collect_run_window_catalog_rows(db_session, city, city_runs)
    run_window_counts = _build_counts(run_window_rows)

    logger.info(
        "run_window_scope city=%s run_window_catalog_total=%s run_window_agenda_catalog_total=%s "
        "historical_catalog_total=%s historical_agenda_catalog_total=%s touched_hashes=%s",
        city,
        run_window_counts["catalog_total"],
        run_window_counts["agenda_catalog_total"],
        historical_counts["catalog_total"],
        historical_counts["agenda_catalog_total"],
        touched_hash_count,
    )

    return CityMetrics(
        run_count=len(city_runs),
        crawl_success_count=crawl_success_count,
        search_success_count=search_success_count,
        catalog_total=historical_counts["catalog_total"],
        agenda_catalog_total=historical_counts["agenda_catalog_total"],
        extraction_non_empty_count=historical_counts["extraction_non_empty_count"],
        segmentation_complete_empty_count=historical_counts["segmentation_complete_empty_count"],
        segmentation_failed_count=historical_counts["segmentation_failed_count"],
        run_window_catalog_total=run_window_counts["catalog_total"],
        run_window_agenda_catalog_total=run_window_counts["agenda_catalog_total"],
        run_window_extraction_non_empty_count=run_window_counts["extraction_non_empty_count"],
        run_window_segmentation_complete_empty_count=run_window_counts["segmentation_complete_empty_count"],
        run_window_segmentation_failed_count=run_window_counts["segmentation_failed_count"],
    )


def _evaluate_city(city: str, metrics: CityMetrics) -> dict[str, Any]:
    crawl_success_rate = _safe_rate(metrics.crawl_success_count, metrics.run_count)
    extraction_non_empty_rate = _safe_rate(
        metrics.run_window_extraction_non_empty_count,
        metrics.run_window_catalog_total,
    )
    segmentation_complete_empty_rate = _safe_rate(
        metrics.run_window_segmentation_complete_empty_count,
        metrics.run_window_agenda_catalog_total,
    )
    segmentation_failed_rate = _safe_rate(
        metrics.run_window_segmentation_failed_count,
        metrics.run_window_agenda_catalog_total,
    )

    insufficient_data = (
        metrics.run_count <= 0
        or metrics.run_window_catalog_total <= 0
        or metrics.run_window_agenda_catalog_total <= 0
    )

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
        "agenda_catalog_total": metrics.agenda_catalog_total,
        "extraction_non_empty_count": metrics.extraction_non_empty_count,
        "segmentation_complete_empty_count": metrics.segmentation_complete_empty_count,
        "segmentation_failed_count": metrics.segmentation_failed_count,
        "run_window_catalog_total": metrics.run_window_catalog_total,
        "run_window_agenda_catalog_total": metrics.run_window_agenda_catalog_total,
        "run_window_extraction_non_empty_count": metrics.run_window_extraction_non_empty_count,
        "run_window_segmentation_complete_empty_count": metrics.run_window_segmentation_complete_empty_count,
        "run_window_segmentation_failed_count": metrics.run_window_segmentation_failed_count,
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
        "| city | quality_gate | run_window_catalog_total | historical_catalog_total | crawl_success_rate | extraction_non_empty_rate | segmentation_complete_empty_rate | segmentation_failed_rate | failed_gates |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            "| {city} | {quality_gate} | {run_window_catalog_total} | {catalog_total} | {crawl_success_rate} | {extraction_non_empty_rate} | {segmentation_complete_empty_rate} | {segmentation_failed_rate} | {failed_gates} |".format(
                city=row["city"],
                quality_gate=row["quality_gate"],
                run_window_catalog_total=row["run_window_catalog_total"],
                catalog_total=row["catalog_total"],
                crawl_success_rate="-" if row["crawl_success_rate"] is None else f"{row['crawl_success_rate']:.3f}",
                extraction_non_empty_rate="-" if row["extraction_non_empty_rate"] is None else f"{row['extraction_non_empty_rate']:.3f}",
                segmentation_complete_empty_rate="-" if row["segmentation_complete_empty_rate"] is None else f"{row['segmentation_complete_empty_rate']:.3f}",
                segmentation_failed_rate="-" if row["segmentation_failed_rate"] is None else f"{row['segmentation_failed_rate']:.3f}",
                failed_gates=", ".join(row["failed_gates"]) if row["failed_gates"] else "-",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
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
