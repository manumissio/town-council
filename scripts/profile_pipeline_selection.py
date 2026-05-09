from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from pipeline.agenda_worker import select_catalog_ids_for_agenda_segmentation
from pipeline.models import Catalog, Document, Event, db_connect
from pipeline.run_pipeline import select_catalog_ids_for_processing
from pipeline.tasks import select_catalog_ids_for_summary_hydration


def _selected_city_catalog_ids(db, city: str) -> set[int]:
    aliases = {city.strip().lower().replace(" ", "_"), city.strip().lower().replace("_", " ")}
    rows = (
        db.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .filter(Event.source.in_(sorted(aliases)))
        .all()
    )
    return {int(row[0]) for row in rows}


def select_triage_catalog_ids(limit: int, city: str | None) -> list[int]:
    Session = sessionmaker(bind=db_connect())
    db = Session()
    try:
        city_ids = _selected_city_catalog_ids(db, city) if city else None
        candidates: list[int] = []
        seen: set[int] = set()

        def add_all(ids: list[int]) -> None:
            for catalog_id in ids:
                cid = int(catalog_id)
                if city_ids is not None and cid not in city_ids:
                    continue
                if cid in seen:
                    continue
                seen.add(cid)
                candidates.append(cid)
                if len(candidates) >= limit:
                    return

        add_all(select_catalog_ids_for_processing(db))
        if len(candidates) < limit:
            add_all(select_catalog_ids_for_agenda_segmentation(db, limit=limit * 2))
        if len(candidates) < limit:
            add_all(select_catalog_ids_for_summary_hydration(db, limit=limit * 2, city=city))
        if len(candidates) < limit:
            fallback_query = (
                db.query(Catalog.id)
                .join(Document, Document.catalog_id == Catalog.id)
                .filter(Catalog.content.isnot(None), Catalog.content != "")
                .order_by(Catalog.id.desc())
            )
            for row in fallback_query.limit(limit * 4).all():
                add_all([int(row[0])])
                if len(candidates) >= limit:
                    break
        return candidates[:limit]
    finally:
        db.close()
