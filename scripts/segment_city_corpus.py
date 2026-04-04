#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import and_, func, or_

from pipeline.backlog_maintenance import capture_agenda_fallback_events, segment_catalog_with_mode, segment_timeout_override
from pipeline.city_scope import source_aliases_for_city
from pipeline.config import CITY_SEGMENTATION_WORKERS, LOCAL_AI_ALLOW_MULTIPROCESS, LOCAL_AI_BACKEND, LOCAL_AI_REQUIRE_SOLO_POOL
from pipeline.db_session import db_session
from pipeline.models import AgendaItem, Catalog, Document, Event

DEFAULT_CATALOG_TIMEOUT_SECONDS = 120
logger = logging.getLogger("segment_city_corpus")


def _html_location_predicate(column):
    value = func.lower(func.coalesce(column, ""))
    return or_(value.like("%.html"), value.like("%.htm"))


def _catalog_ids_for_city(city: str, *, limit: int | None = None, resume_after_id: int | None = None) -> list[int]:
    aliases = sorted(source_aliases_for_city(city))
    with db_session() as session:
        # Keep staged segmentation aligned with summary routing: HTML agendas are
        # still real agendas, so they belong in the actionable backlog queue.
        rows = (
            session.query(Catalog.id)
            .join(Document, Catalog.id == Document.catalog_id)
            .join(Event, Document.event_id == Event.id)
            .outerjoin(AgendaItem, Catalog.id == AgendaItem.catalog_id)
            .filter(
                Document.category.in_(("agenda", "agenda_html")),
                Catalog.content.is_not(None),
                Catalog.content != "",
                Event.source.in_(aliases),
                Catalog.id > resume_after_id if resume_after_id is not None else True,
                # We retry rows that have never been segmented, rows that errored,
                # and "complete" rows whose stored items are missing page metadata.
                # "empty" stays excluded because it is treated as a terminal no-items result.
                or_(
                    Catalog.agenda_segmentation_status == None,
                    Catalog.agenda_segmentation_status == "failed",
                    and_(
                        Catalog.agenda_segmentation_status == "complete",
                        AgendaItem.page_number == None,
                    ),
                ),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        if limit is not None:
            rows = rows.limit(limit)
        rows = rows.all()
    return [row[0] for row in rows]


def _prioritized_catalog_ids(city: str, catalog_ids: list[int]) -> list[int]:
    if not catalog_ids:
        return []
    aliases = sorted(source_aliases_for_city(city))
    with db_session() as session:
        # We inspect sibling agenda locations so HTML-backed meetings can be
        # attempted before weaker PDF variants from the same event.
        rows = (
            session.query(Catalog.id, Catalog.location, Event.id)
            .join(Document, Catalog.id == Document.catalog_id)
            .join(Event, Document.event_id == Event.id)
            .filter(
                Catalog.id.in_(catalog_ids),
                Event.source.in_(aliases),
            )
            .all()
        )
        event_ids = sorted({int(row[2]) for row in rows})
        html_event_ids = {
            int(row[0])
            for row in session.query(Document.event_id)
            .join(Catalog, Catalog.id == Document.catalog_id)
            .join(Event, Document.event_id == Event.id)
            .filter(
                Document.event_id.in_(event_ids),
                Document.category == "agenda",
                Event.source.in_(aliases),
                _html_location_predicate(Catalog.location),
            )
            .distinct()
            .all()
        }

    metadata_by_catalog_id = {
        int(catalog_id): {
            "location": location,
            "event_id": int(event_id),
        }
        for catalog_id, location, event_id in rows
    }

    def _priority(catalog_id: int) -> tuple[int, int]:
        metadata = metadata_by_catalog_id[int(catalog_id)]
        # Direct HTML agendas usually preserve structure better than scanned PDFs,
        # so they get first priority when we have a choice.
        if metadata["location"] and metadata["location"].lower().endswith((".html", ".htm")):
            return (0, int(catalog_id))
        if metadata["event_id"] in html_event_ids:
            return (1, int(catalog_id))
        return (2, int(catalog_id))

    return sorted((int(catalog_id) for catalog_id in catalog_ids), key=_priority)


def _catalog_status(catalog_id: int) -> str | None:
    with db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if catalog is None:
            return None
        return catalog.agenda_segmentation_status


def _mark_catalog_failed(catalog_id: int, message: str) -> None:
    with db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if catalog is None:
            return
        catalog.agenda_segmentation_status = "failed"
        catalog.agenda_segmentation_item_count = 0
        catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
        catalog.agenda_segmentation_error = message[:500]
        session.commit()


def _catalog_timeout_seconds() -> int:
    raw_value = os.getenv("CITY_SEGMENTATION_TIMEOUT_SECONDS", str(DEFAULT_CATALOG_TIMEOUT_SECONDS))
    try:
        return max(1, int(raw_value))
    except ValueError as exc:
        raise ValueError(f"invalid CITY_SEGMENTATION_TIMEOUT_SECONDS: {raw_value}") from exc


def _catalog_worker_count(requested_workers: int | None = None) -> int:
    raw_value = requested_workers if requested_workers is not None else CITY_SEGMENTATION_WORKERS
    try:
        workers = max(1, int(raw_value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid CITY_SEGMENTATION_WORKERS: {raw_value}") from exc

    # In-process LocalAI remains single-worker by default so city maintenance
    # cannot silently bypass the existing multiprocessing guardrails.
    if (LOCAL_AI_BACKEND or "http").strip().lower() == "inprocess" and (
        not LOCAL_AI_ALLOW_MULTIPROCESS or LOCAL_AI_REQUIRE_SOLO_POOL
    ):
        return 1
    return workers


def _segment_catalog_inline(
    catalog_id: int,
    *,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
) -> dict[str, int | str | None]:
    with segment_timeout_override(agenda_timeout_seconds), capture_agenda_fallback_events() as fallback_counts:
        result = segment_catalog_with_mode(catalog_id, segment_mode=segment_mode)
    result["timeout_fallbacks"] = int(fallback_counts.get("timeout", 0))
    result["empty_response_fallbacks"] = int(fallback_counts.get("empty_response", 0))
    result["llm_timeout_then_fallback"] = int(fallback_counts.get("timeout", 0))
    return result


def _segment_catalog_subprocess(
    catalog_id: int,
    timeout_seconds: int,
    *,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
) -> tuple[str, float, dict[str, int | str | None]]:
    started_at = time.monotonic()
    # Each catalog runs in its own short-lived subprocess so a bad segmentation
    # attempt can time out cleanly without poisoning the parent batch runner.
    command = [
        sys.executable,
        "-c",
        (
            "import json; "
            "from scripts.segment_city_corpus import _segment_catalog_inline; "
            f"print(json.dumps(_segment_catalog_inline({catalog_id}, segment_mode={segment_mode!r}, agenda_timeout_seconds={agenda_timeout_seconds!r})))"
        ),
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        duration_seconds = time.monotonic() - started_at
        message = f"agenda_segmentation_timeout:{timeout_seconds}s"
        _mark_catalog_failed(catalog_id, message)
        detail = (exc.stderr or exc.stdout or message).strip() or message
        return "timed_out", duration_seconds, {"status": "timed_out", "detail": detail}
    except subprocess.CalledProcessError as exc:
        duration_seconds = time.monotonic() - started_at
        message = (exc.stderr or exc.stdout or f"agenda_segmentation_subprocess_failed:{exc.returncode}").strip()
        _mark_catalog_failed(catalog_id, message)
        return "failed", duration_seconds, {"status": "failed", "detail": message}

    duration_seconds = time.monotonic() - started_at
    try:
        payload = json.loads((completed.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        message = "agenda_segmentation_invalid_subprocess_payload"
        _mark_catalog_failed(catalog_id, message)
        return "failed", duration_seconds, {"status": "failed", "detail": message}
    status = str(payload.get("status") or "failed")
    if status in {"complete", "empty", "failed", "other"}:
        return status, duration_seconds, payload
    message = "agenda_segmentation_missing_terminal_status"
    _mark_catalog_failed(catalog_id, message)
    return "failed", duration_seconds, {"status": "failed", "detail": message}


def _segment_catalog_batch(
    city: str,
    catalog_ids: list[int],
    *,
    timeout_seconds: int,
    workers: int,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
    progress_callback: Callable[[str, int, int, int, str, float], None] | None = None,
) -> dict[str, int | str]:
    counts = {
        "complete": 0,
        "empty": 0,
        "failed": 0,
        "timed_out": 0,
        "other": 0,
        "timeout_fallbacks": 0,
        "empty_response_fallbacks": 0,
        "llm_attempted": 0,
        "llm_skipped_heuristic_first": 0,
        "heuristic_complete": 0,
        "llm_timeout_then_fallback": 0,
    }
    total_catalogs = len(catalog_ids)
    if total_catalogs == 0:
        return {"city": city, "catalog_count": 0, **counts}

    # Single-worker mode keeps the control flow easy to reason about during
    # guarded maintenance runs, while higher worker counts fan out subprocesses
    # only on the HTTP backend.
    if workers <= 1:
        for index, catalog_id in enumerate(catalog_ids, start=1):
            outcome, duration_seconds, detail = _segment_catalog_subprocess(
                int(catalog_id),
                timeout_seconds,
                segment_mode=segment_mode,
                agenda_timeout_seconds=agenda_timeout_seconds,
            )
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
            if progress_callback:
                progress_callback(city, index, total_catalogs, catalog_id, outcome, duration_seconds)
        return {"city": city, "catalog_count": total_catalogs, **counts}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_position = {
            executor.submit(
                _segment_catalog_subprocess,
                int(catalog_id),
                timeout_seconds,
                segment_mode=segment_mode,
                agenda_timeout_seconds=agenda_timeout_seconds,
            ): (index, catalog_id)
            for index, catalog_id in enumerate(catalog_ids, start=1)
        }
        for future in concurrent.futures.as_completed(future_to_position):
            index, catalog_id = future_to_position[future]
            outcome, duration_seconds, detail = future.result()
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
            if progress_callback:
                progress_callback(city, index, total_catalogs, catalog_id, outcome, duration_seconds)

    return {"city": city, "catalog_count": total_catalogs, **counts}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="Segment agenda catalogs for one city corpus")
    parser.add_argument("--city", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume-after-id", type=int, default=None, dest="resume_after_id")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--segment-mode", choices=("normal", "maintenance"), default="normal")
    parser.add_argument("--agenda-timeout-seconds", type=int, default=None, dest="agenda_timeout_seconds")
    args = parser.parse_args()

    selected_catalog_ids = _catalog_ids_for_city(args.city, limit=args.limit, resume_after_id=args.resume_after_id)
    if not selected_catalog_ids:
        print(f"no agenda catalogs require segmentation for city={args.city}")
        return 0

    timeout_seconds = _catalog_timeout_seconds()
    workers = _catalog_worker_count(args.workers)
    catalog_ids = _prioritized_catalog_ids(args.city, selected_catalog_ids)

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

    counts = _segment_catalog_batch(
        args.city,
        catalog_ids,
        timeout_seconds=timeout_seconds,
        workers=workers,
        segment_mode=args.segment_mode,
        agenda_timeout_seconds=args.agenda_timeout_seconds,
        progress_callback=_log_progress,
    )

    print(
        (
            "segmented city={city} catalog_count={total} complete={complete} empty={empty} "
            "failed={failed} timed_out={timed_out} llm_attempted={llm_attempted} "
            "llm_skipped_heuristic_first={llm_skipped_heuristic_first} heuristic_complete={heuristic_complete} "
            "timeout_fallbacks={timeout_fallbacks}"
        ).format(
            city=args.city,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
