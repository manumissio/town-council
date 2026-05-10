#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import time
from typing import Any

from pipeline import llm as llm_mod
from pipeline import llm_provider as llm_provider_mod
from pipeline.backlog_maintenance import (
    build_deterministic_agenda_summary_payload as _build_deterministic_agenda_summary_payload,
    capture_agenda_fallback_events as _capture_agenda_fallback_events,
    looks_structured_enough_for_heuristic_segmentation as _looks_structured_enough_for_heuristic_segmentation,
    segment_catalog_with_mode as _segment_one_catalog,
    segment_timeout_override as _segment_timeout_override,
    summarize_catalog_with_maintenance_mode as _summarize_catalog_with_maintenance_mode,
    summary_timeout_override as _summary_timeout_override,
)
from pipeline.city_scope import source_aliases_for_city
from pipeline.config import CITY_SEGMENTATION_WORKERS, TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR
from pipeline.db_session import db_session
from pipeline.extraction_service import reextract_catalog_content
from pipeline.indexer import reindex_catalog
from pipeline.maintenance_run_status import MaintenanceRunStatus
from pipeline.tasks import embed_catalog_task, generate_summary_task
from scripts.hydration_counts import ProgressCallback, empty_repaired_summary_counts, rate_per_second
from scripts.hydration_output import emit_progress, emit_stage_timing
from scripts.hydration_repaired_extract import extract_one_catalog, run_extract_city
from scripts.hydration_repaired_runner import run_cli
from scripts.hydration_repaired_segment import run_segment_city
from scripts.hydration_repaired_selectors import (
    apply_url_substring_filter,
    select_extract_catalog_ids,
    select_segment_catalog_ids,
    select_summary_catalog_ids,
    selector_mode,
    usable_local_artifact_status,
)
from scripts.hydration_repaired_summary import run_summary_city, summarize_one_catalog
from scripts.operator_cli import nonnegative_int as _nonnegative_int
from scripts.operator_cli import positive_int as _positive_int
from scripts.operator_cli import safe_run_id as _safe_run_id


def _emit_progress(enabled: bool, message: str) -> None:
    return emit_progress(enabled, message)


def _empty_summary_counts() -> dict[str, int]:
    return empty_repaired_summary_counts()


def _default_segment_workers() -> int:
    try:
        parallelism = int(os.getenv("OLLAMA_NUM_PARALLEL", "1"))
    except ValueError:
        parallelism = 1
    return max(1, min(CITY_SEGMENTATION_WORKERS, max(1, parallelism)))


def _rate_per_second(total: int, elapsed_seconds: float) -> float:
    return rate_per_second(total, elapsed_seconds)


def _usable_local_artifact_status(location: str | None) -> str | None:
    return usable_local_artifact_status(location)


def _selector_mode(url_substring: str | None) -> str:
    return selector_mode(url_substring)


def _apply_url_substring_filter(query: Any, url_substring: str | None) -> Any:
    return apply_url_substring_filter(query, url_substring)


def _select_extract_catalog_ids(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None = None,
) -> tuple[list[int], dict[str, int]]:
    return select_extract_catalog_ids(
        db_session=db_session,
        source_aliases_for_city=source_aliases_for_city,
        artifact_status_checker=_usable_local_artifact_status,
        city=city,
        limit=limit,
        resume_after_id=resume_after_id,
        url_substring=url_substring,
    )


def _select_segment_catalog_ids(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    catalog_ids: list[int] | None = None,
    url_substring: str | None = None,
) -> list[int]:
    return select_segment_catalog_ids(
        db_session=db_session,
        source_aliases_for_city=source_aliases_for_city,
        city=city,
        limit=limit,
        resume_after_id=resume_after_id,
        catalog_ids=catalog_ids,
        url_substring=url_substring,
    )


def _select_summary_catalog_ids(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    catalog_ids: list[int] | None = None,
    url_substring: str | None = None,
) -> list[int]:
    return select_summary_catalog_ids(
        db_session=db_session,
        source_aliases_for_city=source_aliases_for_city,
        city=city,
        limit=limit,
        resume_after_id=resume_after_id,
        catalog_ids=catalog_ids,
        url_substring=url_substring,
    )


def _extract_one_catalog(catalog_id: int) -> tuple[str, dict[str, Any]]:
    return extract_one_catalog(
        catalog_id,
        db_session=db_session,
        reextract_catalog_content=reextract_catalog_content,
        min_extracted_chars=TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
    )


def _run_extract_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress: bool,
    progress_every: int,
    workers: int,
    status_callback: ProgressCallback | None = None,
) -> tuple[dict[str, int], list[int]]:
    return run_extract_city(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        url_substring=url_substring,
        emit_progress_enabled=emit_progress,
        progress_every=progress_every,
        workers=workers,
        select_extract_catalog_ids=_select_extract_catalog_ids,
        extract_one_catalog=_extract_one_catalog,
        status_callback=status_callback,
    )


def _run_segment_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress: bool,
    progress_every: int,
    catalog_ids: list[int] | None = None,
    workers: int = 1,
    agenda_timeout_seconds: int | None = None,
    segment_mode: str = "normal",
    status_callback: ProgressCallback | None = None,
) -> dict[str, int]:
    return run_segment_city(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        url_substring=url_substring,
        emit_progress_enabled=emit_progress,
        progress_every=progress_every,
        select_segment_catalog_ids=_select_segment_catalog_ids,
        segment_one_catalog=_segment_one_catalog,
        segment_timeout_override=_segment_timeout_override,
        capture_agenda_fallback_events=_capture_agenda_fallback_events,
        catalog_ids=catalog_ids,
        workers=workers,
        agenda_timeout_seconds=agenda_timeout_seconds,
        segment_mode=segment_mode,
        status_callback=status_callback,
    )


def _summarize_one_catalog(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
) -> dict[str, Any]:
    return summarize_one_catalog(
        catalog_id,
        summarize_catalog_with_maintenance_mode=_summarize_catalog_with_maintenance_mode,
        build_deterministic_agenda_summary_payload=_build_deterministic_agenda_summary_payload,
        generate_summary_task=generate_summary_task,
        embed_catalog_task=embed_catalog_task,
        reindex_catalog=reindex_catalog,
        summary_fallback_mode=summary_fallback_mode,
    )


def _run_summary_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress: bool,
    progress_every: int,
    catalog_ids: list[int] | None = None,
    summary_timeout_seconds: int | None = None,
    summary_fallback_mode: str = "none",
    status_callback: ProgressCallback | None = None,
) -> dict[str, int]:
    return run_summary_city(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        url_substring=url_substring,
        emit_progress_enabled=emit_progress,
        progress_every=progress_every,
        select_summary_catalog_ids=_select_summary_catalog_ids,
        summarize_one_catalog=_summarize_one_catalog,
        summary_timeout_override=_summary_timeout_override,
        catalog_ids=catalog_ids,
        summary_timeout_seconds=summary_timeout_seconds,
        summary_fallback_mode=summary_fallback_mode,
        status_callback=status_callback,
    )


def _emit_stage_timing(city: str, stage: str, counts: dict[str, int], elapsed_seconds: float) -> None:
    return emit_stage_timing(city, stage, counts, elapsed_seconds)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hydrate repaired city agenda catalogs that still need extraction")
    parser.add_argument("--city", default="san_mateo")
    parser.add_argument("--limit", type=_positive_int, default=None, help="Stage selection limit")
    parser.add_argument("--resume-after-id", type=_nonnegative_int, default=None, dest="resume_after_id")
    parser.add_argument("--url-substring", default=None, help="Optional substring to narrow repaired catalog selection to one source URL family")
    parser.add_argument("--run-id", type=_safe_run_id, default=None)
    parser.add_argument("--output-dir", default="experiments/results/maintenance")
    parser.add_argument("--progress-every", type=_positive_int, default=25)
    parser.add_argument("--extract-workers", type=_positive_int, default=4)
    parser.add_argument("--segment-workers", type=_positive_int, default=_default_segment_workers())
    parser.add_argument("--segment-mode", choices=("normal", "maintenance"), default="normal")
    parser.add_argument("--agenda-timeout-seconds", type=_positive_int, default=None, dest="agenda_timeout_seconds")
    parser.add_argument("--summary-timeout-seconds", type=_positive_int, default=None, dest="summary_timeout_seconds")
    parser.add_argument("--summary-fallback-mode", choices=("none", "deterministic"), default="none")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    return parser


def main() -> int:
    return run_cli(
        _build_parser().parse_args(),
        maintenance_run_status_cls=MaintenanceRunStatus,
        run_extract_city=_run_extract_city,
        run_segment_city=_run_segment_city,
        run_summary_city=_run_summary_city,
        time_module=time,
    )


if __name__ == "__main__":
    raise SystemExit(main())
