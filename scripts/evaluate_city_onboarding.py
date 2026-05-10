#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker

from pipeline.city_onboarding_gate import evaluate_city, safe_rate, write_markdown
from pipeline.city_onboarding_metrics import (
    CityMetrics,
    ISO_FMT,
    build_counts,
    collect_city_metrics,
    collect_historical_city_catalog_rows,
    collect_run_window_catalog_rows,
    load_city_metadata_slugs,
    load_runs,
    ocd_division_id_for_city,
    parse_iso_utc,
    source_aliases_for_city,
)
from pipeline.models import Catalog, Document, Event, UrlStage, UrlStageHist, db_connect
from pipeline.rollout_registry import load_rollout_entry


logger = logging.getLogger("city_onboarding_eval")


_parse_iso_utc = parse_iso_utc
_safe_rate = safe_rate
_ocd_division_id_for_city = ocd_division_id_for_city
_build_counts = build_counts
_load_city_metadata_slugs = load_city_metadata_slugs
_source_aliases_for_city = source_aliases_for_city
_load_runs = load_runs
_collect_historical_city_catalog_rows = collect_historical_city_catalog_rows
_collect_run_window_catalog_rows = collect_run_window_catalog_rows
_collect_city_metrics = collect_city_metrics
_write_markdown = write_markdown


def _evaluate_city(city: str, metrics: CityMetrics) -> dict[str, Any]:
    return evaluate_city(city, metrics, rollout_loader=load_rollout_entry)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate city onboarding quality gates")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--cities", default="")
    parser.add_argument("--output-dir", default="experiments/results/city_onboarding")
    return parser.parse_args()


def _select_cities(rows: list[dict[str, Any]], requested_csv: str) -> list[str]:
    valid_city_slugs = _load_city_metadata_slugs()
    requested = [city.strip() for city in requested_csv.split(",") if city.strip()]
    if not requested:
        return sorted({row["city"] for row in rows})

    unknown = [city for city in requested if city not in valid_city_slugs]
    if unknown:
        raise SystemExit(f"Unknown city slug(s): {', '.join(unknown)}")
    return requested


def _evaluate_selected_cities(
    rows: list[dict[str, Any]],
    selected_cities: list[str],
) -> list[dict[str, Any]]:
    by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["city"] in selected_cities:
            by_city[row["city"]].append(row)

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        return [
            _evaluate_city(city, _collect_city_metrics(session, city, by_city.get(city, [])))
            for city in selected_cities
        ]
    finally:
        session.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = _parse_args()

    run_dir = Path(args.output_dir) / args.run_id
    runs_path = run_dir / "runs.jsonl"

    rows = _load_runs(runs_path)
    if not rows:
        raise SystemExit(f"No run rows found: {runs_path}")

    selected_cities = _select_cities(rows, args.cities)
    results = _evaluate_selected_cities(rows, selected_cities)

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
