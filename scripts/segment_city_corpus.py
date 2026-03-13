#!/usr/bin/env python3
from __future__ import annotations

import argparse

from sqlalchemy import and_, or_

from pipeline.agenda_worker import segment_document_agenda
from pipeline.db_session import db_session
from pipeline.models import AgendaItem, Catalog, Document, Event


def _source_aliases_for_city(city: str) -> set[str]:
    aliases = {city}
    legacy_aliases = {
        "san_mateo": {"san mateo"},
        "san_leandro": {"san leandro"},
        "mtn_view": {"mountain view"},
    }
    aliases.update(legacy_aliases.get(city, set()))
    return aliases


def _catalog_ids_for_city(city: str) -> list[int]:
    aliases = sorted(_source_aliases_for_city(city))
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Segment agenda catalogs for one city corpus")
    parser.add_argument("--city", required=True)
    args = parser.parse_args()

    catalog_ids = _catalog_ids_for_city(args.city)
    if not catalog_ids:
        print(f"no agenda catalogs require segmentation for city={args.city}")
        return 0

    for catalog_id in catalog_ids:
        segment_document_agenda(int(catalog_id))

    print(f"segmented city={args.city} catalog_count={len(catalog_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
