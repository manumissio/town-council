#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import and_, or_

from pipeline.agenda_worker import segment_document_agenda
from pipeline.city_scope import source_aliases_for_city
from pipeline.db_session import db_session
from pipeline.models import AgendaItem, Catalog, Document, Event

DEFAULT_CATALOG_TIMEOUT_SECONDS = 120
logger = logging.getLogger("segment_city_corpus")


def _catalog_ids_for_city(city: str) -> list[int]:
    aliases = sorted(source_aliases_for_city(city))
    with db_session() as session:
        rows = (
            session.query(Catalog.id)
            .join(Document, Catalog.id == Document.catalog_id)
            .join(Event, Document.event_id == Event.id)
            .outerjoin(AgendaItem, Catalog.id == AgendaItem.catalog_id)
            .filter(
                Document.category == "agenda",
                Catalog.content.is_not(None),
                Catalog.content != "",
                Event.source.in_(aliases),
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
            .all()
        )
    return [row[0] for row in rows]


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


def _segment_catalog_subprocess(catalog_id: int, timeout_seconds: int) -> tuple[str, float, str | None]:
    started_at = time.monotonic()
    command = [
        sys.executable,
        "-c",
        f"from pipeline.agenda_worker import segment_document_agenda; segment_document_agenda({catalog_id})",
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
        return "timed_out", duration_seconds, detail
    except subprocess.CalledProcessError as exc:
        duration_seconds = time.monotonic() - started_at
        message = (exc.stderr or exc.stdout or f"agenda_segmentation_subprocess_failed:{exc.returncode}").strip()
        _mark_catalog_failed(catalog_id, message)
        return "failed", duration_seconds, message

    duration_seconds = time.monotonic() - started_at
    status = _catalog_status(catalog_id)
    if status in {"complete", "empty", "failed"}:
        detail = completed.stderr.strip() or completed.stdout.strip() or None
        return status, duration_seconds, detail

    message = "agenda_segmentation_missing_terminal_status"
    _mark_catalog_failed(catalog_id, message)
    return "failed", duration_seconds, message


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="Segment agenda catalogs for one city corpus")
    parser.add_argument("--city", required=True)
    args = parser.parse_args()

    catalog_ids = _catalog_ids_for_city(args.city)
    if not catalog_ids:
        print(f"no agenda catalogs require segmentation for city={args.city}")
        return 0

    timeout_seconds = _catalog_timeout_seconds()
    counts = {
        "complete": 0,
        "empty": 0,
        "failed": 0,
        "timed_out": 0,
    }

    for catalog_id in catalog_ids:
        logger.info("segmentation_catalog_start city=%s catalog_id=%s timeout_seconds=%s", args.city, catalog_id, timeout_seconds)
        outcome, duration_seconds, detail = _segment_catalog_subprocess(int(catalog_id), timeout_seconds)
        counts[outcome] += 1
        logger.info(
            "segmentation_catalog_finish city=%s catalog_id=%s outcome=%s duration_seconds=%.2f detail=%s",
            args.city,
            catalog_id,
            outcome,
            duration_seconds,
            detail or "",
        )

    print(
        "segmented city={city} catalog_count={total} complete={complete} empty={empty} failed={failed} timed_out={timed_out}".format(
            city=args.city,
            total=len(catalog_ids),
            complete=counts["complete"],
            empty=counts["empty"],
            failed=counts["failed"],
            timed_out=counts["timed_out"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
