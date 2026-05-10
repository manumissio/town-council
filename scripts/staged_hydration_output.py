from __future__ import annotations

import argparse
import json
from typing import Any


def emit_final_output(args: argparse.Namespace, all_runs: list[dict[str, Any]]) -> None:
    if args.json:
        payload: dict[str, Any] = {"cities": all_runs[-1]["cities"]}
        if args.repeat_until_idle:
            payload["runs"] = all_runs
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print("Staged City Hydration")
    print("=====================")
    if args.repeat_until_idle:
        print(f"runs: {len(all_runs)}")
    for city_result in all_runs[-1]["cities"]:
        print(f"city: {city_result['city']}")
        print(f"  before_missing_summary_total: {city_result['before']['missing_summary_total']}")
        print(f"  after_missing_summary_total: {city_result['after']['missing_summary_total']}")
        print(f"  chunks: {len(city_result['chunks'])}")
        print(f"  segmentation: {city_result['segmentation']}")
        print(f"  summary: {city_result['summary']}")
        print(f"  delta: {city_result['delta']}")


def emit_before_snapshot(city: str, before_snapshot: dict[str, Any], human_progress: bool, emit_progress_callable) -> None:
    emit_progress_callable(
        human_progress,
        "[{city}] before_snapshot missing_summary_total={missing} catalogs_with_summary={summaries} "
        "agenda_missing_without_items={agenda_without_items} agenda_missing_with_items={agenda_with_items} "
        "non_agenda_missing={non_agenda_missing}".format(
            city=city,
            missing=before_snapshot["missing_summary_total"],
            summaries=before_snapshot["catalogs_with_summary"],
            agenda_without_items=before_snapshot["agenda_missing_summary_without_items"],
            agenda_with_items=before_snapshot["agenda_missing_summary_with_items"],
            non_agenda_missing=before_snapshot["non_agenda_missing_summary_total"],
        ),
    )


def emit_chunk_finish(
    city: str,
    chunk_index: int,
    after_snapshot: dict[str, Any],
    segmentation: dict[str, Any],
    delta: dict[str, Any],
    human_progress: bool,
    emit_progress_callable,
) -> None:
    emit_progress_callable(
        human_progress,
        "[{city}] chunk_finish chunk={chunk} after_missing_summary_total={missing} "
        "resume_after_id={resume_after_id} delta={delta}".format(
            city=city,
            chunk=chunk_index,
            missing=after_snapshot["missing_summary_total"],
            resume_after_id=segmentation["last_catalog_id"],
            delta=delta,
        ),
    )


def emit_city_finish(city: str, after_snapshot: dict[str, Any], delta: dict[str, Any], human_progress: bool, emit_progress_callable) -> None:
    emit_progress_callable(
        human_progress,
        "[{city}] city_finish after_missing_summary_total={missing} catalogs_with_summary={summaries} delta={delta}".format(
            city=city,
            missing=after_snapshot["missing_summary_total"],
            summaries=after_snapshot["catalogs_with_summary"],
            delta=delta,
        ),
    )
