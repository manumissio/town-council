from __future__ import annotations

import argparse
import concurrent.futures
import logging
from typing import Callable

from scripts.segment_city_contracts import (
    ProgressCallback,
    SegmentPayload,
    SegmentWorkerServices,
    empty_segment_counts,
)

logger = logging.getLogger("segment_city_corpus")


def segment_catalog_batch(
    city: str,
    catalog_ids: list[int],
    *,
    timeout_seconds: int,
    workers: int,
    segment_catalog_subprocess: Callable[..., tuple[str, float, SegmentPayload]],
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, int | str]:
    counts = empty_segment_counts()
    total_catalogs = len(catalog_ids)
    if total_catalogs == 0:
        return {"city": city, "catalog_count": 0, **counts}
    if workers <= 1:
        _run_serial(
            city,
            catalog_ids,
            counts,
            _BatchServices(segment_catalog_subprocess),
            _BatchOptions(timeout_seconds, segment_mode, agenda_timeout_seconds, progress_callback),
        )
    else:
        _run_parallel(
            city,
            catalog_ids,
            counts,
            _BatchServices(segment_catalog_subprocess),
            _BatchOptions(timeout_seconds, segment_mode, agenda_timeout_seconds, progress_callback),
            workers,
        )
    return {"city": city, "catalog_count": total_catalogs, **counts}


class _BatchServices:
    def __init__(self, segment_catalog_subprocess: Callable[..., tuple[str, float, SegmentPayload]]):
        self.segment_catalog_subprocess = segment_catalog_subprocess


class _BatchOptions:
    def __init__(
        self,
        timeout_seconds: int,
        segment_mode: str,
        agenda_timeout_seconds: int | None,
        progress_callback: ProgressCallback | None,
    ):
        self.timeout_seconds = timeout_seconds
        self.segment_mode = segment_mode
        self.agenda_timeout_seconds = agenda_timeout_seconds
        self.progress_callback = progress_callback


def _run_serial(
    city: str,
    catalog_ids: list[int],
    counts: dict[str, int],
    services: _BatchServices,
    options: _BatchOptions,
) -> None:
    total_catalogs = len(catalog_ids)
    for index, catalog_id in enumerate(catalog_ids, start=1):
        outcome, duration_seconds, detail = services.segment_catalog_subprocess(
            int(catalog_id),
            options.timeout_seconds,
            segment_mode=options.segment_mode,
            agenda_timeout_seconds=options.agenda_timeout_seconds,
        )
        _record_outcome(counts, detail, outcome)
        if options.progress_callback:
            options.progress_callback(city, index, total_catalogs, catalog_id, outcome, duration_seconds)


def _run_parallel(
    city: str,
    catalog_ids: list[int],
    counts: dict[str, int],
    services: _BatchServices,
    options: _BatchOptions,
    workers: int,
) -> None:
    total_catalogs = len(catalog_ids)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_position = {
            executor.submit(
                services.segment_catalog_subprocess,
                int(catalog_id),
                options.timeout_seconds,
                segment_mode=options.segment_mode,
                agenda_timeout_seconds=options.agenda_timeout_seconds,
            ): (index, catalog_id)
            for index, catalog_id in enumerate(catalog_ids, start=1)
        }
        for future in concurrent.futures.as_completed(future_to_position):
            index, catalog_id = future_to_position[future]
            outcome, duration_seconds, detail = future.result()
            _record_outcome(counts, detail, outcome)
            if options.progress_callback:
                options.progress_callback(city, index, total_catalogs, catalog_id, outcome, duration_seconds)


def _record_outcome(counts: dict[str, int], detail: SegmentPayload, outcome: str) -> None:
    counts[outcome] += 1
    if isinstance(detail, dict):
        for key in (
            "timeout_fallbacks",
            "empty_response_fallbacks",
            "llm_attempted",
            "llm_skipped_heuristic_first",
            "heuristic_complete",
            "llm_timeout_then_fallback",
        ):
            counts[key] += int(detail.get(key, 0))


def run_cli(
    args: argparse.Namespace,
    *,
    catalog_ids_for_city: Callable[..., list[int]],
    prioritized_catalog_ids: Callable[[str, list[int]], list[int]],
    catalog_timeout_seconds: Callable[[], int],
    catalog_worker_count: Callable[[int | None], int],
    segment_catalog_batch_callable: Callable[..., dict[str, int | str]],
) -> int:
    selected_catalog_ids = catalog_ids_for_city(args.city, limit=args.limit, resume_after_id=args.resume_after_id)
    if not selected_catalog_ids:
        print(f"no agenda catalogs require segmentation for city={args.city}")
        return 0

    timeout_seconds = catalog_timeout_seconds()
    workers = catalog_worker_count(args.workers)
    catalog_ids = prioritized_catalog_ids(args.city, selected_catalog_ids)
    counts = segment_catalog_batch_callable(
        args.city,
        catalog_ids,
        timeout_seconds=timeout_seconds,
        workers=workers,
        segment_mode=args.segment_mode,
        agenda_timeout_seconds=args.agenda_timeout_seconds,
        progress_callback=_log_progress,
    )
    _print_summary(args.city, counts)
    return 0


def _log_progress(city: str, index: int, total_catalogs: int, catalog_id: int, outcome: str, duration_seconds: float) -> None:
    logger.info(
        "segmentation_catalog_finish city=%s index=%s/%s catalog_id=%s outcome=%s duration_seconds=%.2f",
        city,
        index,
        total_catalogs,
        catalog_id,
        outcome,
        duration_seconds,
    )


def _print_summary(city: str, counts: dict[str, int | str]) -> None:
    print(
        (
            "segmented city={city} catalog_count={total} complete={complete} empty={empty} "
            "failed={failed} timed_out={timed_out} llm_attempted={llm_attempted} "
            "llm_skipped_heuristic_first={llm_skipped_heuristic_first} heuristic_complete={heuristic_complete} "
            "timeout_fallbacks={timeout_fallbacks}"
        ).format(
            city=city,
            total=counts["catalog_count"],
            complete=counts["complete"],
            empty=counts["empty"],
            failed=counts["failed"],
            timed_out=counts["timed_out"],
            llm_attempted=counts["llm_attempted"],
            llm_skipped_heuristic_first=counts["llm_skipped_heuristic_first"],
            heuristic_complete=counts["heuristic_complete"],
            timeout_fallbacks=counts["timeout_fallbacks"],
        )
    )
