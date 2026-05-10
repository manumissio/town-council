from __future__ import annotations

from sqlalchemy import and_

from pipeline.city_scope import source_aliases_for_city
from pipeline.db_session import db_session
from pipeline.indexer import reindex_catalog
from pipeline.models import AgendaItem, Catalog, Document, Event, SemanticEmbedding
from scripts.laserfiche_repair_contracts import RepairTarget
from scripts.laserfiche_repair_pdf_io import is_valid_pdf_artifact


def select_targets(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    salvage_bad_electronicfile: bool = False,
) -> list[RepairTarget]:
    with db_session() as session:
        query = (
            session.query(Catalog.id, Catalog.url, Catalog.location)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Event.id == Document.event_id)
            .outerjoin(AgendaItem, AgendaItem.catalog_id == Catalog.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                AgendaItem.id.is_(None),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        if salvage_bad_electronicfile:
            query = query.filter(
                Catalog.url.ilike("%/ElectronicFile.aspx%"),
                Catalog.content.is_(None),
            )
        else:
            query = query.filter(Catalog.url.ilike("%/DocView.aspx%"))
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        if limit is not None:
            query = query.limit(limit)
        rows = query.all()
    targets = [
        RepairTarget(
            catalog_id=row[0],
            old_url=row[1],
            location=row[2],
            mode="salvage" if salvage_bad_electronicfile else "docview",
        )
        for row in rows
    ]
    if salvage_bad_electronicfile:
        return [target for target in targets if not is_valid_pdf_artifact(target.location)]
    return targets


def apply_repairs(repairs: list[dict[str, object]], *, reindex: bool) -> dict[str, int]:
    counts = {"updated": 0, "skipped_duplicate_hash": 0}
    reindex_ids: list[int] = []

    with db_session() as session:
        for repair in repairs:
            catalog_id = int(repair["catalog_id"])
            new_hash = str(repair["new_hash"])
            existing = (
                session.query(Catalog.id)
                .filter(Catalog.url_hash == new_hash, Catalog.id != catalog_id)
                .first()
            )
            if existing:
                counts["skipped_duplicate_hash"] += 1
                continue

            catalog = session.get(Catalog, catalog_id)
            if not catalog:
                continue

            _mutate_catalog(catalog, repair, new_hash)
            session.query(SemanticEmbedding).filter(SemanticEmbedding.catalog_id == catalog_id).delete(
                synchronize_session=False
            )
            session.query(Document).filter(
                and_(Document.catalog_id == catalog_id, Document.category == "agenda")
            ).update(
                {
                    Document.url: str(repair["new_url"]),
                    Document.url_hash: new_hash,
                },
                synchronize_session=False,
            )

            counts["updated"] += 1
            if reindex:
                reindex_ids.append(catalog_id)

        session.commit()

    for catalog_id in reindex_ids:
        reindex_catalog(catalog_id)

    return counts


def _mutate_catalog(catalog: Catalog, repair: dict[str, object], new_hash: str) -> None:
    catalog.url = str(repair["new_url"])
    catalog.url_hash = new_hash
    catalog.location = str(repair["path"])
    catalog.filename = str(repair["filename"])

    catalog.content = None
    catalog.content_hash = None
    catalog.extraction_status = "pending"
    catalog.extraction_attempted_at = None
    catalog.extraction_attempt_count = 0
    catalog.extraction_error = None

    catalog.summary = None
    catalog.summary_source_hash = None
    catalog.summary_extractive = None
    catalog.entities = None
    catalog.topics = None
    catalog.topics_source_hash = None

    catalog.agenda_segmentation_status = None
    catalog.agenda_segmentation_attempted_at = None
    catalog.agenda_segmentation_item_count = None
    catalog.agenda_segmentation_error = None
