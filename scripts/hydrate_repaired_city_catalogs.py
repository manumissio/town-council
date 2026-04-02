#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from sqlalchemy import and_, or_

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
from pipeline.config import (
    CITY_SEGMENTATION_WORKERS,
    TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
)
from pipeline.db_session import db_session
from pipeline.extraction_service import reextract_catalog_content
from pipeline.indexer import reindex_catalog
from pipeline.maintenance_run_status import MaintenanceRunStatus, validate_run_id
from pipeline import llm as llm_mod
from pipeline import llm_provider as llm_provider_mod
from pipeline.models import AgendaItem, Catalog, Document, Event
from pipeline.tasks import embed_catalog_task, generate_summary_task


ProgressCallback = Callable[[dict[str, Any]], None]


def _emit_progress(enabled: bool, message: str) -> None:
    if enabled:
        print(message, flush=True)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return parsed


def _safe_run_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _empty_summary_counts() -> dict[str, int]:
    return {
        "selected": 0,
        "complete": 0,
        "cached": 0,
        "stale": 0,
        "blocked_low_signal": 0,
        "blocked_ungrounded": 0,
        "not_generated_yet": 0,
        "error": 0,
        "other": 0,
        "agenda_deterministic_complete": 0,
        "llm_complete": 0,
        "deterministic_fallback_complete": 0,
    }


def _default_segment_workers() -> int:
    try:
        parallelism = int(os.getenv("OLLAMA_NUM_PARALLEL", "1"))
    except ValueError:
        parallelism = 1
    return max(1, min(CITY_SEGMENTATION_WORKERS, max(1, parallelism)))


def _rate_per_second(total: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        return 0.0
    return total / elapsed_seconds


def _usable_local_artifact_status(location: str | None) -> str | None:
    if not location:
        return "missing_file"
    if not os.path.exists(location):
        return "missing_file"
    if os.path.getsize(location) <= 0:
        return "zero_byte"
    return None


def _selector_mode(url_substring: str | None) -> str:
    if url_substring:
        return f"url_substring:{url_substring}"
    return "city_agenda_repair"


def _apply_url_substring_filter(query: Any, url_substring: str | None) -> Any:
    if not url_substring:
        return query
    # Repaired agenda hydration should default to city/state selection and only
    # use URL-shape filters when an operator explicitly wants a narrower batch.
    return query.filter(Catalog.url.ilike(f"%{url_substring}%"))


def _select_extract_catalog_ids(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None = None,
) -> tuple[list[int], dict[str, int]]:
    with db_session() as session:
        query = (
            session.query(Catalog.id, Catalog.location)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                Catalog.content.is_(None),
            )
            .order_by(Catalog.id)
        )
        query = _apply_url_substring_filter(query, url_substring)
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        rows = query.order_by(Catalog.id).all()

    counts = {"missing_file": 0, "zero_byte": 0}
    selected_ids: list[int] = []
    for catalog_id, location in rows:
        invalid_status = _usable_local_artifact_status(location)
        if invalid_status:
            counts[invalid_status] += 1
            continue
        selected_ids.append(catalog_id)
        if limit is not None and len(selected_ids) >= limit:
            break
    return selected_ids, counts


def _select_segment_catalog_ids(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    catalog_ids: list[int] | None = None,
    url_substring: str | None = None,
) -> list[int]:
    with db_session() as session:
        query = (
            session.query(Catalog.id)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .outerjoin(AgendaItem, AgendaItem.catalog_id == Catalog.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                Catalog.content.is_not(None),
                Catalog.content != "",
                or_(
                    Catalog.agenda_segmentation_status.is_(None),
                    Catalog.agenda_segmentation_status == "failed",
                    and_(
                        Catalog.agenda_segmentation_status == "complete",
                        AgendaItem.page_number.is_(None),
                    ),
                ),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        query = _apply_url_substring_filter(query, url_substring)
        if catalog_ids is not None:
            if not catalog_ids:
                return []
            query = query.filter(Catalog.id.in_(catalog_ids))
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        if limit is not None:
            query = query.limit(limit)
        return [row[0] for row in query.all()]


def _select_summary_catalog_ids(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    catalog_ids: list[int] | None = None,
    url_substring: str | None = None,
) -> list[int]:
    with db_session() as session:
        query = (
            session.query(Catalog.id)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .join(AgendaItem, AgendaItem.catalog_id == Catalog.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                Catalog.content.is_not(None),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        query = _apply_url_substring_filter(query, url_substring)
        if catalog_ids is not None:
            if not catalog_ids:
                return []
            query = query.filter(Catalog.id.in_(catalog_ids))
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        if limit is not None:
            query = query.limit(limit)
        return [row[0] for row in query.all()]


def _extract_one_catalog(catalog_id: int) -> tuple[str, dict[str, Any]]:
    with db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if not catalog:
            return "missing_catalog", {"error": "Catalog not found"}
        if not catalog.location:
            return "missing_file", {"error": "Catalog has no file location"}
        if not os.path.exists(catalog.location):
            return "missing_file", {"error": "File not found on disk", "location": catalog.location}
        if os.path.getsize(catalog.location) <= 0:
            return "zero_byte", {"error": "Zero-byte file on disk", "location": catalog.location}

        result = reextract_catalog_content(
            catalog,
            force=True,
            ocr_fallback=True,
            min_chars=TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
        )
        session.commit()

    if "error" in result:
        return "failed", result
    status = str(result.get("status") or "other")
    if status == "updated":
        return "updated", result
    if status == "cached":
        return "cached", result
    return "other", result


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
    catalog_ids, precheck_counts = _select_extract_catalog_ids(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        url_substring=url_substring,
    )
    counts = {
        "selected": len(catalog_ids),
        "updated": 0,
        "cached": 0,
        "missing_file": precheck_counts["missing_file"],
        "zero_byte": precheck_counts["zero_byte"],
        "missing_catalog": 0,
        "failed": 0,
        "other": 0,
    }
    ready_catalog_ids: list[int] = []
    _emit_progress(
        emit_progress,
        f"[{city}] extract_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id} "
        f"selector={_selector_mode(url_substring)!r}",
    )
    if status_callback:
        status_callback(
            {
                "event_type": "stage_start",
                "stage": "extract",
                "counts": counts.copy(),
                "detail": {"selector_mode": _selector_mode(url_substring)},
            }
        )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_extract_one_catalog, catalog_id): catalog_id for catalog_id in catalog_ids}
        for index, future in enumerate(as_completed(futures), start=1):
            catalog_id = futures[future]
            status, detail = future.result()
            counts[status] = counts.get(status, 0) + 1
            if status in {"updated", "cached"}:
                ready_catalog_ids.append(catalog_id)
            if emit_progress and (index == 1 or index % progress_every == 0 or index == len(catalog_ids)):
                extra = ""
                if "error" in detail:
                    extra = f" last_error={detail['error']!r}"
                _emit_progress(
                    True,
                    f"[{city}] extract_progress done={index}/{len(catalog_ids)} last_catalog_id={catalog_id} "
                    f"last_status={status} counts={counts}{extra}",
                )
            if status_callback and (index == 1 or index % progress_every == 0 or index == len(catalog_ids)):
                status_callback(
                    {
                        "event_type": "progress",
                        "stage": "extract",
                        "counts": counts.copy(),
                        "last_catalog_id": catalog_id,
                        "detail": {"done": index, "total": len(catalog_ids), "last_status": status},
                    }
                )
    ready_catalog_ids.sort()
    _emit_progress(emit_progress, f"[{city}] extract_finish counts={counts}")
    if status_callback:
        status_callback({"event_type": "stage_finish", "stage": "extract", "counts": counts.copy()})
    return counts, ready_catalog_ids


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
    selected_catalog_ids = _select_segment_catalog_ids(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        catalog_ids=catalog_ids,
        url_substring=url_substring,
    )
    counts = {
        "selected": len(selected_catalog_ids),
        "complete": 0,
        "empty": 0,
        "failed": 0,
        "other": 0,
        "timeout_fallbacks": 0,
        "empty_response_fallbacks": 0,
        "llm_attempted": 0,
        "llm_skipped_heuristic_first": 0,
        "heuristic_complete": 0,
        "llm_timeout_then_fallback": 0,
    }
    _emit_progress(
        emit_progress,
        f"[{city}] segment_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id} "
        f"selector={_selector_mode(url_substring)!r}",
    )
    if status_callback:
        status_callback(
            {
                "event_type": "stage_start",
                "stage": "segment",
                "counts": counts.copy(),
                "detail": {"selector_mode": _selector_mode(url_substring)},
            }
        )
    with _segment_timeout_override(agenda_timeout_seconds), _capture_agenda_fallback_events() as fallback_counts:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_segment_one_catalog, catalog_id, segment_mode=segment_mode): catalog_id
                for catalog_id in selected_catalog_ids
            }
            for index, future in enumerate(as_completed(futures), start=1):
                catalog_id = futures[future]
                result = future.result()
                status = str(result.get("status") or "other")
                counts[status] = counts.get(status, 0) + 1
                counts["llm_attempted"] += int(result.get("llm_attempted", 0))
                counts["llm_skipped_heuristic_first"] += int(result.get("llm_skipped_heuristic_first", 0))
                counts["heuristic_complete"] += int(result.get("heuristic_complete", 0))
                counts["timeout_fallbacks"] = int(fallback_counts.get("timeout", 0))
                counts["empty_response_fallbacks"] = int(fallback_counts.get("empty_response", 0))
                counts["llm_timeout_then_fallback"] = counts["timeout_fallbacks"]
                if emit_progress and (index == 1 or index % progress_every == 0 or index == len(selected_catalog_ids)):
                    _emit_progress(
                        True,
                        f"[{city}] segment_progress done={index}/{len(selected_catalog_ids)} last_catalog_id={catalog_id} "
                        f"last_status={status} counts={counts}",
                    )
                if status_callback and (index == 1 or index % progress_every == 0 or index == len(selected_catalog_ids)):
                    status_callback(
                        {
                            "event_type": "progress",
                            "stage": "segment",
                            "counts": counts.copy(),
                            "last_catalog_id": catalog_id,
                            "detail": {"done": index, "total": len(selected_catalog_ids), "last_status": status},
                        }
                    )
    _emit_progress(emit_progress, f"[{city}] segment_finish counts={counts}")
    if status_callback:
        status_callback({"event_type": "stage_finish", "stage": "segment", "counts": counts.copy()})
    return counts


def _summarize_one_catalog(
    catalog_id: int,
    *,
    summary_fallback_mode: str = "none",
) -> dict[str, Any]:
    try:
        return _summarize_catalog_with_maintenance_mode(
            catalog_id,
            summary_fallback_mode=summary_fallback_mode,
            generate_summary_callable=lambda target_catalog_id: generate_summary_task.run(target_catalog_id, force=False),
            deterministic_summary_callable=lambda target_catalog_id: _build_deterministic_agenda_summary_payload(
                target_catalog_id,
                reindex_callback=reindex_catalog,
                embed_callback=lambda summary_catalog_id: embed_catalog_task.delay(summary_catalog_id),
            ),
        )
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


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
    selected_catalog_ids = _select_summary_catalog_ids(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        catalog_ids=catalog_ids,
        url_substring=url_substring,
    )
    counts = _empty_summary_counts()
    counts["selected"] = len(selected_catalog_ids)
    _emit_progress(
        emit_progress,
        f"[{city}] summary_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id} "
        f"selector={_selector_mode(url_substring)!r}",
    )
    if status_callback:
        status_callback(
            {
                "event_type": "stage_start",
                "stage": "summary",
                "counts": counts.copy(),
                "detail": {"selector_mode": _selector_mode(url_substring)},
            }
        )
    with _summary_timeout_override(summary_timeout_seconds):
        for index, catalog_id in enumerate(selected_catalog_ids, start=1):
            result = _summarize_one_catalog(catalog_id, summary_fallback_mode=summary_fallback_mode)
            status = str(result.get("status") or "other")
            if status in counts:
                counts[status] += 1
            else:
                counts["other"] += 1
            completion_mode = str(result.get("completion_mode") or "")
            if completion_mode == "agenda_deterministic":
                counts["agenda_deterministic_complete"] += 1
            elif completion_mode == "llm":
                counts["llm_complete"] += 1
            elif completion_mode == "deterministic_fallback":
                counts["deterministic_fallback_complete"] += 1
            if emit_progress and (index == 1 or index % progress_every == 0 or index == len(selected_catalog_ids)):
                extra = f" last_error={result['error']!r}" if "error" in result else ""
                if completion_mode:
                    extra += f" completion_mode={completion_mode!r}"
                _emit_progress(
                    True,
                    f"[{city}] summary_progress done={index}/{len(selected_catalog_ids)} last_catalog_id={catalog_id} "
                    f"last_status={status} counts={counts}{extra}",
                )
            if status_callback and (index == 1 or index % progress_every == 0 or index == len(selected_catalog_ids)):
                status_callback(
                    {
                        "event_type": "progress",
                        "stage": "summary",
                        "counts": counts.copy(),
                        "last_catalog_id": catalog_id,
                        "detail": {"done": index, "total": len(selected_catalog_ids), "last_status": status},
                    }
                )
    _emit_progress(emit_progress, f"[{city}] summary_finish counts={counts}")
    if status_callback:
        status_callback({"event_type": "stage_finish", "stage": "summary", "counts": counts.copy()})
    return counts


def _emit_stage_timing(city: str, stage: str, counts: dict[str, int], elapsed_seconds: float) -> None:
    selected = int(counts.get("selected", 0))
    completed = sum(int(counts.get(key, 0)) for key in ("updated", "cached", "complete"))
    print(
        f"[{city}] {stage}_timing elapsed_s={elapsed_seconds:.2f} "
        f"selected={selected} completed={completed} rate_per_s={_rate_per_second(completed, elapsed_seconds):.2f}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Hydrate repaired city agenda catalogs that still need extraction")
    parser.add_argument("--city", default="san_mateo")
    parser.add_argument("--limit", type=_positive_int, default=None, help="Stage selection limit")
    parser.add_argument("--resume-after-id", type=_nonnegative_int, default=None, dest="resume_after_id")
    parser.add_argument(
        "--url-substring",
        default=None,
        help="Optional substring to narrow repaired catalog selection to one source URL family",
    )
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
    args = parser.parse_args()

    emit_progress = not args.json
    run_status = MaintenanceRunStatus(
        tool_name="hydrate_repaired_city_catalogs",
        output_dir=args.output_dir,
        run_id=args.run_id,
        metadata={
            "city": args.city,
            "selector_mode": _selector_mode(args.url_substring),
            "args": {
                "limit": args.limit,
                "resume_after_id": args.resume_after_id,
                "url_substring": args.url_substring,
                "progress_every": args.progress_every,
                "extract_workers": args.extract_workers,
                "segment_workers": args.segment_workers,
                "segment_mode": args.segment_mode,
                "agenda_timeout_seconds": args.agenda_timeout_seconds,
                "summary_timeout_seconds": args.summary_timeout_seconds,
                "summary_fallback_mode": args.summary_fallback_mode,
                "json": args.json,
            },
        },
    )
    if emit_progress:
        print(
            f"[{args.city}] run_status run_id={run_status.run_id} artifact_dir={run_status.paths.run_dir}",
            flush=True,
        )

    def _status_callback(event: dict[str, Any]) -> None:
        stage = str(event["stage"])
        counts = dict(event["counts"])
        last_catalog_id = event.get("last_catalog_id")
        detail = dict(event.get("detail") or {})
        event_type = str(event["event_type"])
        progress = None
        if event_type == "progress":
            progress = {key: detail[key] for key in ("done", "total", "last_status") if key in detail}
        run_status.heartbeat(
            status="running",
            stage=stage,
            counts=counts,
            last_catalog_id=last_catalog_id if isinstance(last_catalog_id, int) else None,
            progress=progress,
        )
        run_status.event(
            event_type=event_type,
            stage=stage,
            counts=counts,
            last_catalog_id=last_catalog_id if isinstance(last_catalog_id, int) else None,
            detail=detail or None,
        )

    started = time.perf_counter()
    status = "failed"
    payload: dict[str, Any] | None = None
    failure_message: str | None = None
    try:
        extract_started = time.perf_counter()
        extract_counts, extracted_catalog_ids = _run_extract_city(
            args.city,
            limit=args.limit,
            resume_after_id=args.resume_after_id,
            url_substring=args.url_substring,
            emit_progress=emit_progress,
            progress_every=args.progress_every,
            workers=args.extract_workers,
            status_callback=_status_callback,
        )
        extract_elapsed = time.perf_counter() - extract_started
        if emit_progress:
            _emit_stage_timing(args.city, "extract", extract_counts, extract_elapsed)

        segment_started = time.perf_counter()
        segment_counts = _run_segment_city(
            args.city,
            limit=args.limit,
            resume_after_id=args.resume_after_id,
            url_substring=args.url_substring,
            emit_progress=emit_progress,
            progress_every=args.progress_every,
            catalog_ids=extracted_catalog_ids,
            workers=args.segment_workers,
            agenda_timeout_seconds=args.agenda_timeout_seconds,
            segment_mode=args.segment_mode,
            status_callback=_status_callback,
        )
        segment_elapsed = time.perf_counter() - segment_started
        if emit_progress:
            _emit_stage_timing(args.city, "segment", segment_counts, segment_elapsed)

        summary_started = time.perf_counter()
        summary_counts = _run_summary_city(
            args.city,
            limit=args.limit,
            resume_after_id=args.resume_after_id,
            url_substring=args.url_substring,
            emit_progress=emit_progress,
            progress_every=args.progress_every,
            catalog_ids=extracted_catalog_ids,
            summary_timeout_seconds=args.summary_timeout_seconds,
            summary_fallback_mode=args.summary_fallback_mode,
            status_callback=_status_callback,
        )
        summary_elapsed = time.perf_counter() - summary_started
        if emit_progress:
            _emit_stage_timing(args.city, "summary", summary_counts, summary_elapsed)

        payload = {
            "city": args.city,
            "selector_mode": _selector_mode(args.url_substring),
            "url_substring": args.url_substring,
            "resume_after_id": args.resume_after_id,
            "limit": args.limit,
            "progress_every": args.progress_every,
            "extract_workers": args.extract_workers,
            "segment_workers": args.segment_workers,
            "segment_mode": args.segment_mode,
            "agenda_timeout_seconds": args.agenda_timeout_seconds,
            "summary_timeout_seconds": args.summary_timeout_seconds,
            "summary_fallback_mode": args.summary_fallback_mode,
            "extract": extract_counts,
            "segment": segment_counts,
            "summary": summary_counts,
            "timing": {
                "extract_seconds": round(extract_elapsed, 4),
                "segment_seconds": round(segment_elapsed, 4),
                "summary_seconds": round(summary_elapsed, 4),
                "extract_rate_per_s": round(
                    _rate_per_second(extract_counts.get("updated", 0) + extract_counts.get("cached", 0), extract_elapsed),
                    4,
                ),
                "segment_rate_per_s": round(_rate_per_second(segment_counts.get("complete", 0), segment_elapsed), 4),
                "summary_rate_per_s": round(_rate_per_second(summary_counts.get("complete", 0), summary_elapsed), 4),
            },
        }
        status = "completed"
        run_status.heartbeat(status="completed", stage="complete", counts=payload)
        run_status.event(event_type="completed", stage="complete", counts=payload)
        run_status.result(
            status="completed",
            counts=payload,
            elapsed_seconds=time.perf_counter() - started,
        )

        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"[{args.city}] hydrate_finish payload={payload}", flush=True)
        return 0
    except Exception as exc:
        failure_message = str(exc)
        raise
    finally:
        if status != "completed":
            failure_payload = payload or {
                "city": args.city,
                "selector_mode": _selector_mode(args.url_substring),
                "url_substring": args.url_substring,
            }
            run_status.heartbeat(status="failed", stage="failed", counts=failure_payload)
            run_status.event(
                event_type="failed",
                stage="failed",
                counts=failure_payload,
                detail={"error": failure_message or "unknown_error"},
            )
            run_status.result(
                status="failed",
                counts=failure_payload,
                elapsed_seconds=time.perf_counter() - started,
                error=failure_message or "unknown_error",
            )


if __name__ == "__main__":
    raise SystemExit(main())
