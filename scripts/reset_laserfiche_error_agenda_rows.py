#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from pipeline.city_scope import source_aliases_for_city
from pipeline.agenda_resolver import has_viable_structured_agenda_source
from pipeline.db_session import db_session
from pipeline.indexer import reindex_catalog
from pipeline.laserfiche_error_pages import DOCUMENT_SHAPE_FAMILY, classify_catalog_bad_content
from pipeline.models import AgendaItem, Catalog, Document, Event, SemanticEmbedding


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _matching_catalog_classifications(
    city: str,
    *,
    limit: int | None = None,
    include_document_shape: bool = False,
) -> dict[int, tuple[str, str]]:
    with db_session() as session:
        query = (
            session.query(Catalog, Document)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Event.id == Document.event_id)
            .filter(Event.source.in_(sorted(source_aliases_for_city(city))))
            .filter(Document.category == "agenda")
            .filter(Catalog.content.is_not(None))
            .order_by(Catalog.id, Document.id)
        )
        if limit is not None:
            query = query.limit(limit)
        rows = query.all()
        matches: dict[int, tuple[str, str]] = {}
        for catalog, doc in rows:
            if int(catalog.id) in matches:
                continue
            classification = classify_catalog_bad_content(catalog)
            if classification:
                matches[int(catalog.id)] = (classification.family, classification.reason)
                continue
            if not include_document_shape:
                continue
            classification = classify_catalog_bad_content(
                catalog,
                document_category=getattr(doc, "category", None),
                include_document_shape=True,
                has_viable_structured_source=has_viable_structured_agenda_source(session, catalog, doc),
            )
            if classification and (
                classification.family != DOCUMENT_SHAPE_FAMILY or catalog.summary is None
            ):
                matches[int(catalog.id)] = (classification.family, classification.reason)
        return matches


def _report(city: str, *, limit: int | None = None, include_document_shape: bool = False) -> dict[str, Any]:
    matching_classifications = _matching_catalog_classifications(
        city,
        limit=limit,
        include_document_shape=include_document_shape,
    )
    matching_ids = list(matching_classifications.keys())
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
        "matched_empty": sum(1 for row in rows if row[2] == "empty"),
        "matched_failed": sum(1 for row in rows if row[2] == "failed"),
        "matched_unresolved": sum(1 for row in rows if row[1] is None),
        "matched_with_items": len(item_catalog_ids),
        "matched_with_summary": sum(1 for row in rows if row[1]),
        "family_counts": {
            family: sum(1 for matched_family, _ in matching_classifications.values() if matched_family == family)
            for family in sorted({family for family, _ in matching_classifications.values()})
        },
        "reason_counts": {
            reason: sum(1 for _, matched_reason in matching_classifications.values() if matched_reason == reason)
            for reason in sorted({reason for _, reason in matching_classifications.values()})
        },
        "sample_catalog_ids": matching_ids[:10],
    }


def _reset_catalog_state(catalog: Catalog, *, reason: str) -> None:
    # These rows are classifier-matched backlog artifacts, so we clear both the stored
    # source text and the derived artifacts before reprocessing.
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
    catalog.extraction_error = reason
    catalog.extraction_attempt_count = 0
    catalog.extraction_attempted_at = None
    catalog.processed = False


def _apply_reset(city: str, *, limit: int | None = None, include_document_shape: bool = False) -> dict[str, Any]:
    matching_classifications = _matching_catalog_classifications(
        city,
        limit=limit,
        include_document_shape=include_document_shape,
    )
    matching_ids = list(matching_classifications.keys())
    reset_catalog_ids: list[int] = []
    reset_family_counts: dict[str, int] = {}
    reset_reason_counts: dict[str, int] = {}
    with db_session() as session:
        rows = (
            session.query(Catalog, Document)
            .join(Document, Document.catalog_id == Catalog.id)
            .filter(Catalog.id.in_(matching_ids or [-1]))
            .order_by(Catalog.id, Document.id)
            .all()
        )
        seen_catalog_ids: set[int] = set()
        for catalog, doc in rows:
            if int(catalog.id) in seen_catalog_ids:
                continue
            seen_catalog_ids.add(int(catalog.id))
            classification = classify_catalog_bad_content(catalog)
            if not classification:
                if not include_document_shape:
                    continue
                classification = classify_catalog_bad_content(
                    catalog,
                    document_category=getattr(doc, "category", None),
                    include_document_shape=True,
                    has_viable_structured_source=has_viable_structured_agenda_source(session, catalog, doc),
                )
                if not classification or (
                    classification.family == DOCUMENT_SHAPE_FAMILY and catalog.summary is not None
                ):
                    continue
            session.query(AgendaItem).filter(AgendaItem.catalog_id == catalog.id).delete(synchronize_session=False)
            session.query(SemanticEmbedding).filter(SemanticEmbedding.catalog_id == catalog.id).delete(synchronize_session=False)
            _reset_catalog_state(catalog, reason=classification.reason)
            reset_catalog_ids.append(int(catalog.id))
            reset_family_counts[classification.family] = int(
                reset_family_counts.get(classification.family, 0)
            ) + 1
            reset_reason_counts[classification.reason] = int(
                reset_reason_counts.get(classification.reason, 0)
            ) + 1
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
        "family_counts": reset_family_counts,
        "reason_counts": reset_reason_counts,
        "sample_catalog_ids": reset_catalog_ids[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset classifier-matched agenda rows so they can be re-extracted cleanly")
    parser.add_argument("--city", default="san_mateo")
    parser.add_argument("--limit", type=_positive_int, default=None)
    parser.add_argument("--include-document-shape", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = _report(args.city, limit=args.limit, include_document_shape=args.include_document_shape)
    result = {"report": report}
    if args.apply:
        result["apply"] = _apply_reset(
            args.city,
            limit=args.limit,
            include_document_shape=args.include_document_shape,
        )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    print("Classifier-Matched Agenda Rows")
    print("=============================")
    print(f"city: {report['city']}")
    print(f"matched_total: {report['matched_total']}")
    print(f"matched_complete: {report['matched_complete']}")
    print(f"matched_empty: {report['matched_empty']}")
    print(f"matched_failed: {report['matched_failed']}")
    print(f"matched_unresolved: {report['matched_unresolved']}")
    print(f"matched_with_items: {report['matched_with_items']}")
    print(f"matched_with_summary: {report['matched_with_summary']}")
    print(f"family_counts: {report['family_counts']}")
    print(f"reason_counts: {report['reason_counts']}")
    print(f"sample_catalog_ids: {report['sample_catalog_ids']}")
    if args.apply:
        print(f"reset_total: {result['apply']['reset_total']}")
        print(f"reindexed_total: {result['apply']['reindexed_total']}")
        print(f"reset_family_counts: {result['apply']['family_counts']}")
        print(f"reset_reason_counts: {result['apply']['reason_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
