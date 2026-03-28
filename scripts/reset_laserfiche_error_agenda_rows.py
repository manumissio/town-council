#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from pipeline.city_scope import source_aliases_for_city
from pipeline.db_session import db_session
from pipeline.indexer import reindex_catalog
from pipeline.laserfiche_error_pages import catalog_has_laserfiche_error_content
from pipeline.models import AgendaItem, Catalog, Document, Event, SemanticEmbedding


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _matching_catalog_ids(city: str, *, limit: int | None = None) -> list[int]:
    with db_session() as session:
        query = (
            session.query(Catalog)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Event.id == Document.event_id)
            .filter(Event.source.in_(sorted(source_aliases_for_city(city))))
            .filter(Document.category == "agenda")
            .filter(Catalog.content.is_not(None))
            .order_by(Catalog.id)
        )
        if limit is not None:
            query = query.limit(limit)
        catalogs = query.all()
        return [int(catalog.id) for catalog in catalogs if catalog_has_laserfiche_error_content(catalog)]


def _report(city: str, *, limit: int | None = None) -> dict[str, Any]:
    matching_ids = _matching_catalog_ids(city, limit=limit)
    with db_session() as session:
        rows = (
            session.query(
                Catalog.id,
                Catalog.summary,
                Catalog.agenda_segmentation_status,
                Catalog.agenda_segmentation_item_count,
            )
            .filter(Catalog.id.in_(matching_ids or [-1]))
            .order_by(Catalog.id)
            .all()
        )
        item_catalog_ids = {
            row[0]
            for row in session.query(AgendaItem.catalog_id)
            .filter(AgendaItem.catalog_id.in_(matching_ids or [-1]))
            .distinct()
            .all()
        }
    return {
        "city": city,
        "matched_total": len(matching_ids),
        "matched_complete": sum(1 for row in rows if row[2] == "complete"),
        "matched_unresolved": sum(1 for row in rows if row[1] is None),
        "matched_with_items": len(item_catalog_ids),
        "matched_with_summary": sum(1 for row in rows if row[1]),
        "sample_catalog_ids": matching_ids[:10],
    }


def _reset_catalog_state(catalog: Catalog) -> None:
    # These rows are poisoned derivatives from a portal error page, so we clear
    # both the bad source text and all derived artifacts before reprocessing.
    catalog.content = None
    catalog.content_hash = None
    catalog.summary = None
    catalog.summary_source_hash = None
    catalog.summary_extractive = None
    catalog.entities = None
    catalog.tables = None
    catalog.topics = None
    catalog.topics_source_hash = None
    catalog.agenda_segmentation_status = None
    catalog.agenda_segmentation_attempted_at = None
    catalog.agenda_segmentation_item_count = None
    catalog.agenda_segmentation_error = None
    catalog.extraction_status = "pending"
    catalog.extraction_error = "laserfiche_error_page_detected"
    catalog.extraction_attempt_count = 0
    catalog.extraction_attempted_at = None
    catalog.processed = False


def _apply_reset(city: str, *, limit: int | None = None) -> dict[str, Any]:
    matching_ids = _matching_catalog_ids(city, limit=limit)
    reset_catalog_ids: list[int] = []
    with db_session() as session:
        catalogs = (
            session.query(Catalog)
            .filter(Catalog.id.in_(matching_ids or [-1]))
            .order_by(Catalog.id)
            .all()
        )
        for catalog in catalogs:
            if not catalog_has_laserfiche_error_content(catalog):
                continue
            session.query(AgendaItem).filter(AgendaItem.catalog_id == catalog.id).delete(synchronize_session=False)
            session.query(SemanticEmbedding).filter(SemanticEmbedding.catalog_id == catalog.id).delete(synchronize_session=False)
            _reset_catalog_state(catalog)
            reset_catalog_ids.append(int(catalog.id))
        session.commit()

    reindexed = 0
    for catalog_id in reset_catalog_ids:
        try:
            reindex_catalog(catalog_id)
            reindexed += 1
        except Exception:
            pass

    return {
        "city": city,
        "reset_total": len(reset_catalog_ids),
        "reindexed_total": reindexed,
        "sample_catalog_ids": reset_catalog_ids[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset Laserfiche error-page agenda rows so they can be re-extracted cleanly")
    parser.add_argument("--city", default="san_mateo")
    parser.add_argument("--limit", type=_positive_int, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = _report(args.city, limit=args.limit)
    result = {"report": report}
    if args.apply:
        result["apply"] = _apply_reset(args.city, limit=args.limit)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    print("Laserfiche Error Agenda Rows")
    print("============================")
    print(f"city: {report['city']}")
    print(f"matched_total: {report['matched_total']}")
    print(f"matched_complete: {report['matched_complete']}")
    print(f"matched_unresolved: {report['matched_unresolved']}")
    print(f"matched_with_items: {report['matched_with_items']}")
    print(f"matched_with_summary: {report['matched_with_summary']}")
    print(f"sample_catalog_ids: {report['sample_catalog_ids']}")
    if args.apply:
        print(f"reset_total: {result['apply']['reset_total']}")
        print(f"reindexed_total: {result['apply']['reindexed_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
