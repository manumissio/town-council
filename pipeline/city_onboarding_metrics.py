from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_, union_all

from pipeline.models import Catalog, Document, Event, UrlStage, UrlStageHist


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
logger = logging.getLogger("city_onboarding_eval")


@dataclass
class CityMetrics:
    run_count: int
    crawl_success_count: int
    search_success_count: int
    stable_noop_run_count: int
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


def parse_iso_utc(value: str) -> datetime:
    dt = datetime.strptime(value, ISO_FMT)
    return dt.replace(tzinfo=timezone.utc)


def load_city_metadata_slugs(path: Path = Path("city_metadata/list_of_cities.csv")) -> set[str]:
    slugs: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            division = (row.get("ocd_division_id") or "").strip()
            if "/place:" not in division:
                continue
            slugs.add(division.split("/place:", 1)[1])
    return slugs


def source_aliases_for_city(city: str) -> set[str]:
    aliases = {city}
    legacy_aliases = {
        "san_mateo": {"san mateo"},
        "san_leandro": {"san leandro"},
        "mtn_view": {"mountain view"},
    }
    aliases.update(legacy_aliases.get(city, set()))
    return aliases


def ocd_division_id_for_city(city: str) -> str:
    return f"ocd-division/country:us/state:ca/place:{city}"


def load_runs(path: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not path.exists():
        return runs
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        row["started_dt"] = parse_iso_utc(row["started_at_utc"])
        row["finished_dt"] = parse_iso_utc(row["finished_at_utc"])
        runs.append(row)
    return runs


def collect_historical_city_catalog_rows(
    db_session, city: str, city_runs: list[dict[str, Any]]
) -> list[tuple[int, str, str | None, str | None]]:
    windows = [
        (run["started_dt"].replace(tzinfo=None), run["finished_dt"].replace(tzinfo=None))
        for run in city_runs
    ]
    if not windows:
        return []

    source_aliases = sorted(source_aliases_for_city(city))
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

    # Delta crawls can succeed without inserting new events in a run window.
    # Fall back to existing city corpus so historical diagnostics remain useful.
    if not event_ids:
        event_ids = [row[0] for row in db_session.query(Event.id).filter(Event.source.in_(source_aliases)).all()]

    if not event_ids:
        return []

    return (
        db_session.query(Catalog.id, Document.category, Catalog.content, Catalog.agenda_segmentation_status)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Document.event_id.in_(event_ids))
        .all()
    )


def collect_run_window_catalog_rows(
    db_session, city: str, city_runs: list[dict[str, Any]]
) -> tuple[list[tuple[int, str, str | None, str | None]], int]:
    ocd_division_id = ocd_division_id_for_city(city)

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

    # Keep an explicit subquery shape so Postgres and SQLite expose the same columns.
    touched_hashes = union_all(*(query.statement for query in touched_queries)).subquery("touched_hashes")
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
        "run_window_scope city=%s ocd_division_id=%s touched_hashes=%s resolved_catalogs=%s "
        "source=url_stage_hist+url_stage",
        city,
        ocd_division_id,
        touched_hash_count,
        len(catalog_rows),
    )
    return catalog_rows, touched_hash_count


def build_counts(catalog_rows: list[tuple[int, str, str | None, str | None]]) -> dict[str, int]:
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


def collect_city_metrics(db_session, city: str, city_runs: list[dict[str, Any]]) -> CityMetrics:
    crawl_success_count = sum(
        1 for run in city_runs if run.get("crawler_status") in {"success", "crawler_stable_noop"}
    )
    search_success_count = sum(1 for run in city_runs if run.get("search_status") == "success")
    stable_noop_run_count = sum(1 for run in city_runs if run.get("crawler_status") == "crawler_stable_noop")

    historical_counts = build_counts(collect_historical_city_catalog_rows(db_session, city, city_runs))
    run_window_rows, touched_hash_count = collect_run_window_catalog_rows(db_session, city, city_runs)
    run_window_counts = build_counts(run_window_rows)

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
        stable_noop_run_count=stable_noop_run_count,
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
