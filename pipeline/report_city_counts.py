"""
Print per-city ingestion counts from the database.

Why this exists:
When adding a new city (like Cupertino), it's easy to run the crawler and
pipeline but still not be sure if data actually landed where it should.
This script provides a quick, non-UI sanity check without relying on
city-specific expectations.
"""

from __future__ import annotations

import argparse

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from pipeline.models import db_connect, Place, Event, Document, AgendaItem


def _build_counts(db):
    events_ct = (
        db.query(Event.place_id.label("place_id"), func.count(Event.id).label("events"))
        .group_by(Event.place_id)
        .subquery()
    )
    docs_ct = (
        db.query(Document.place_id.label("place_id"), func.count(Document.id).label("documents"))
        .group_by(Document.place_id)
        .subquery()
    )
    catalogs_ct = (
        db.query(
            Document.place_id.label("place_id"),
            func.count(func.distinct(Document.catalog_id)).label("catalogs"),
        )
        .filter(Document.catalog_id.isnot(None))
        .group_by(Document.place_id)
        .subquery()
    )
    agenda_ct = (
        db.query(Event.place_id.label("place_id"), func.count(AgendaItem.id).label("agenda_items"))
        .join(Event, AgendaItem.event_id == Event.id)
        .group_by(Event.place_id)
        .subquery()
    )

    return events_ct, docs_ct, catalogs_ct, agenda_ct


def main() -> int:
    parser = argparse.ArgumentParser(description="Print per-city ingestion counts.")
    parser.add_argument(
        "--filter",
        default="",
        help="Optional case-insensitive substring filter on Place.display_name or Place.name (e.g. 'cupertino').",
    )
    args = parser.parse_args()

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        events_ct, docs_ct, catalogs_ct, agenda_ct = _build_counts(db)

        q = (
            db.query(
                Place.display_name,
                Place.name,
                func.coalesce(events_ct.c.events, 0).label("events"),
                func.coalesce(docs_ct.c.documents, 0).label("documents"),
                func.coalesce(catalogs_ct.c.catalogs, 0).label("catalogs"),
                func.coalesce(agenda_ct.c.agenda_items, 0).label("agenda_items"),
            )
            .outerjoin(events_ct, events_ct.c.place_id == Place.id)
            .outerjoin(docs_ct, docs_ct.c.place_id == Place.id)
            .outerjoin(catalogs_ct, catalogs_ct.c.place_id == Place.id)
            .outerjoin(agenda_ct, agenda_ct.c.place_id == Place.id)
            .order_by(Place.display_name.asc().nulls_last(), Place.name.asc())
        )

        if args.filter:
            f = f"%{args.filter.lower()}%"
            q = q.filter(
                func.lower(func.coalesce(Place.display_name, "")).like(f)
                | func.lower(Place.name).like(f)
            )

        print("display_name,name,events,documents,catalogs,agenda_items")
        for row in q.all():
            print(
                f"{row.display_name or ''},{row.name},{row.events},{row.documents},{row.catalogs},{row.agenda_items}"
            )

        return 0
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

