#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from pipeline.backlog_maintenance import capture_agenda_fallback_events, segment_catalog_with_mode, segment_timeout_override
from pipeline.city_scope import source_aliases_for_city
from pipeline.config import CITY_SEGMENTATION_WORKERS, LOCAL_AI_ALLOW_MULTIPROCESS, LOCAL_AI_BACKEND, LOCAL_AI_REQUIRE_SOLO_POOL
from pipeline.db_session import db_session
from scripts import segment_city_worker as _worker_impl
from scripts.segment_city_contracts import DEFAULT_CATALOG_TIMEOUT_SECONDS
from scripts.segment_city_contracts import SegmentSelectionServices, SegmentWorkerServices
from scripts.segment_city_runner import run_cli, segment_catalog_batch
from scripts.segment_city_selection import catalog_ids_for_city, html_location_predicate, prioritized_catalog_ids

logger = logging.getLogger("segment_city_corpus")

_html_location_predicate = html_location_predicate


def _selection_services() -> SegmentSelectionServices:
    return SegmentSelectionServices(db_session=db_session, source_aliases_for_city=source_aliases_for_city)


def _worker_services() -> SegmentWorkerServices:
    return SegmentWorkerServices(
        db_session=db_session,
        segment_catalog_with_mode=segment_catalog_with_mode,
        segment_timeout_override=segment_timeout_override,
        capture_agenda_fallback_events=capture_agenda_fallback_events,
        mark_catalog_failed=_mark_catalog_failed,
    )


def _sync_worker_config() -> None:
    _worker_impl.CITY_SEGMENTATION_WORKERS = CITY_SEGMENTATION_WORKERS
    _worker_impl.LOCAL_AI_BACKEND = LOCAL_AI_BACKEND
    _worker_impl.LOCAL_AI_ALLOW_MULTIPROCESS = LOCAL_AI_ALLOW_MULTIPROCESS
    _worker_impl.LOCAL_AI_REQUIRE_SOLO_POOL = LOCAL_AI_REQUIRE_SOLO_POOL


def _catalog_ids_for_city(
    city: str,
    *,
    limit: int | None = None,
    resume_after_id: int | None = None,
) -> list[int]:
    return catalog_ids_for_city(_selection_services(), city, limit=limit, resume_after_id=resume_after_id)


def _prioritized_catalog_ids(city: str, catalog_ids: list[int]) -> list[int]:
    return prioritized_catalog_ids(_selection_services(), city, catalog_ids)


def _catalog_status(catalog_id: int) -> str | None:
    return _worker_impl.catalog_status(_worker_services(), catalog_id)


def _mark_catalog_failed(catalog_id: int, message: str) -> None:
    return _worker_impl.mark_catalog_failed(_worker_services(), catalog_id, message)


def _catalog_timeout_seconds() -> int:
    _worker_impl.DEFAULT_CATALOG_TIMEOUT_SECONDS = DEFAULT_CATALOG_TIMEOUT_SECONDS
    return _worker_impl.catalog_timeout_seconds()


def _catalog_worker_count(requested_workers: int | None = None) -> int:
    _sync_worker_config()
    return _worker_impl.catalog_worker_count(requested_workers)


def _segment_catalog_inline(
    catalog_id: int,
    *,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
) -> dict[str, int | str | None]:
    return _worker_impl.segment_catalog_inline(
        _worker_services(),
        catalog_id,
        segment_mode=segment_mode,
        agenda_timeout_seconds=agenda_timeout_seconds,
    )


def _segment_catalog_subprocess(
    catalog_id: int,
    timeout_seconds: int,
    *,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
) -> tuple[str, float, dict[str, int | str | None]]:
    return _worker_impl.segment_catalog_subprocess(
        _worker_services(),
        catalog_id,
        timeout_seconds,
        segment_mode=segment_mode,
        agenda_timeout_seconds=agenda_timeout_seconds,
    )


def _segment_catalog_batch(
    city: str,
    catalog_ids: list[int],
    *,
    timeout_seconds: int,
    workers: int,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
    progress_callback=None,
) -> dict[str, int | str]:
    return segment_catalog_batch(
        city,
        catalog_ids,
        timeout_seconds=timeout_seconds,
        workers=workers,
        segment_catalog_subprocess=_segment_catalog_subprocess,
        segment_mode=segment_mode,
        agenda_timeout_seconds=agenda_timeout_seconds,
        progress_callback=progress_callback,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Segment agenda catalogs for one city corpus")
    parser.add_argument("--city", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume-after-id", type=int, default=None, dest="resume_after_id")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--segment-mode", choices=("normal", "maintenance"), default="normal")
    parser.add_argument("--agenda-timeout-seconds", type=int, default=None, dest="agenda_timeout_seconds")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    return run_cli(
        _parser().parse_args(),
        catalog_ids_for_city=_catalog_ids_for_city,
        prioritized_catalog_ids=_prioritized_catalog_ids,
        catalog_timeout_seconds=_catalog_timeout_seconds,
        catalog_worker_count=_catalog_worker_count,
        segment_catalog_batch_callable=_segment_catalog_batch,
    )


if __name__ == "__main__":
    raise SystemExit(main())
