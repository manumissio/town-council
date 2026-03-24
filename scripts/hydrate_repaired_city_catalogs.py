#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any

from sqlalchemy import and_, or_

from pipeline.agenda_worker import segment_document_agenda
from pipeline.city_scope import source_aliases_for_city
from pipeline.config import TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR
from pipeline.db_session import db_session
from pipeline.extraction_service import reextract_catalog_content
from pipeline.models import AgendaItem, Catalog, Document, Event
from pipeline.tasks import generate_summary_task


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
    }


def _select_extract_catalog_ids(city: str, *, limit: int | None, resume_after_id: int | None) -> list[int]:
    with db_session() as session:
        query = (
            session.query(Catalog.id)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                Catalog.url.ilike("%/ElectronicFile.aspx%"),
                Catalog.content.is_(None),
            )
            .order_by(Catalog.id)
        )
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        if limit is not None:
            query = query.limit(limit)
        return [row[0] for row in query.all()]


def _select_segment_catalog_ids(city: str, *, limit: int | None, resume_after_id: int | None) -> list[int]:
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
                Catalog.url.ilike("%/ElectronicFile.aspx%"),
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
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        if limit is not None:
            query = query.limit(limit)
        return [row[0] for row in query.all()]


def _select_summary_catalog_ids(city: str, *, limit: int | None, resume_after_id: int | None) -> list[int]:
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
                Catalog.url.ilike("%/ElectronicFile.aspx%"),
                Catalog.content.is_not(None),
            )
            .distinct()
            .order_by(Catalog.id)
        )
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
    emit_progress: bool,
    progress_every: int,
) -> dict[str, int]:
    catalog_ids = _select_extract_catalog_ids(city, limit=limit, resume_after_id=resume_after_id)
    counts = {
        "selected": len(catalog_ids),
        "updated": 0,
        "cached": 0,
        "missing_file": 0,
        "zero_byte": 0,
        "missing_catalog": 0,
        "failed": 0,
        "other": 0,
    }
    _emit_progress(
        emit_progress,
        f"[{city}] extract_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id}",
    )
    for index, catalog_id in enumerate(catalog_ids, start=1):
        status, detail = _extract_one_catalog(catalog_id)
        counts[status] = counts.get(status, 0) + 1
        if emit_progress and (index == 1 or index % progress_every == 0 or index == len(catalog_ids)):
            extra = ""
            if "error" in detail:
                extra = f" last_error={detail['error']!r}"
            _emit_progress(
                True,
                f"[{city}] extract_progress done={index}/{len(catalog_ids)} last_catalog_id={catalog_id} "
                f"last_status={status} counts={counts}{extra}",
            )
    _emit_progress(emit_progress, f"[{city}] extract_finish counts={counts}")
    return counts


def _segment_one_catalog(catalog_id: int) -> str:
    segment_document_agenda(catalog_id)
    with db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        return str(getattr(catalog, "agenda_segmentation_status", None) or "other")


def _run_segment_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    emit_progress: bool,
    progress_every: int,
) -> dict[str, int]:
    catalog_ids = _select_segment_catalog_ids(city, limit=limit, resume_after_id=resume_after_id)
    counts = {"selected": len(catalog_ids), "complete": 0, "empty": 0, "failed": 0, "other": 0}
    _emit_progress(
        emit_progress,
        f"[{city}] segment_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id}",
    )
    for index, catalog_id in enumerate(catalog_ids, start=1):
        status = _segment_one_catalog(catalog_id)
        counts[status] = counts.get(status, 0) + 1
        if emit_progress and (index == 1 or index % progress_every == 0 or index == len(catalog_ids)):
            _emit_progress(
                True,
                f"[{city}] segment_progress done={index}/{len(catalog_ids)} last_catalog_id={catalog_id} "
                f"last_status={status} counts={counts}",
            )
    _emit_progress(emit_progress, f"[{city}] segment_finish counts={counts}")
    return counts


def _summarize_one_catalog(catalog_id: int) -> dict[str, Any]:
    return generate_summary_task.run(catalog_id, force=False) or {}


def _run_summary_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    emit_progress: bool,
    progress_every: int,
) -> dict[str, int]:
    catalog_ids = _select_summary_catalog_ids(city, limit=limit, resume_after_id=resume_after_id)
    counts = _empty_summary_counts()
    counts["selected"] = len(catalog_ids)
    _emit_progress(
        emit_progress,
        f"[{city}] summary_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id}",
    )
    for index, catalog_id in enumerate(catalog_ids, start=1):
        result = _summarize_one_catalog(catalog_id)
        status = str(result.get("status") or "other")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
        if emit_progress and (index == 1 or index % progress_every == 0 or index == len(catalog_ids)):
            _emit_progress(
                True,
                f"[{city}] summary_progress done={index}/{len(catalog_ids)} last_catalog_id={catalog_id} "
                f"last_status={status} counts={counts}",
            )
    _emit_progress(emit_progress, f"[{city}] summary_finish counts={counts}")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Hydrate repaired ElectronicFile-backed city agenda catalogs")
    parser.add_argument("--city", default="san_mateo")
    parser.add_argument("--limit", type=_positive_int, default=None, help="Stage selection limit")
    parser.add_argument("--resume-after-id", type=_nonnegative_int, default=None, dest="resume_after_id")
    parser.add_argument("--progress-every", type=_positive_int, default=25)
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    emit_progress = not args.json
    extract_counts = _run_extract_city(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        emit_progress=emit_progress,
        progress_every=args.progress_every,
    )
    segment_counts = _run_segment_city(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        emit_progress=emit_progress,
        progress_every=args.progress_every,
    )
    summary_counts = _run_summary_city(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        emit_progress=emit_progress,
        progress_every=args.progress_every,
    )

    payload = {
        "city": args.city,
        "resume_after_id": args.resume_after_id,
        "limit": args.limit,
        "progress_every": args.progress_every,
        "extract": extract_counts,
        "segment": segment_counts,
        "summary": summary_counts,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"[{args.city}] hydrate_finish payload={payload}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
