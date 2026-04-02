from sqlalchemy.orm import sessionmaker

from pipeline.models import db_connect, Place, Organization, Event
from pipeline.models import Document, Catalog
from pipeline.indexer import reindex_catalogs
from pipeline.profiling import selected_catalog_ids
from pipeline.utils import generate_ocd_id

def run_organization_backfill():
    """
    Migration Script: Populates the new 'organization' table based on existing meetings.
    
    How it works:
    1. It ensures every City (Place) has at least a 'City Council' Organization.
    2. It loops through all meetings (Event).
    3. It guesses the body name (Planning Commission, etc.) or defaults to 'City Council'.
    4. It links the meeting to the correct body ID.
    """
    print("Connecting to database for organization backfill...")
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    scoped_catalog_ids = selected_catalog_ids()
    scoped_place_ids = None
    scoped_event_query = session.query(Event)
    if scoped_catalog_ids:
        scoped_event_query = (
            scoped_event_query.join(Document, Document.event_id == Event.id)
            .join(Catalog, Catalog.id == Document.catalog_id)
            .filter(Catalog.id.in_(sorted(scoped_catalog_ids)))
            .distinct()
        )
        scoped_place_ids = {event.place_id for event in scoped_event_query.all()}

    # 1. Ensure 'City Council' exists for every scoped city.
    places_query = session.query(Place)
    if scoped_place_ids is not None:
        places_query = places_query.filter(Place.id.in_(sorted(scoped_place_ids)))
    places = places_query.all()
    print(f"Ensuring base organizations for {len(places)} cities...")
    for place in places:
        council = session.query(Organization).filter_by(place_id=place.id, name="City Council").first()
        if not council:
            session.add(Organization(
                name="City Council", 
                classification="legislature", 
                place_id=place.id,
                ocd_id=generate_ocd_id('organization')
            ))
    session.flush()

    # 2. Link events
    events = scoped_event_query.all()
    print(f"Found {len(events)} events to process.")

    count = 0
    changed_catalog_ids: set[int] = set()
    for event in events:
        # Determine the Organization name
        org_name = "City Council"
        raw_name = (event.meeting_type or "").lower()
        if "planning commission" in raw_name or "planning board" in raw_name:
            org_name = "Planning Commission"
        elif "parks" in raw_name:
            org_name = "Parks & Recreation Commission"
        
        # Find or Create the body for this specific city
        org = session.query(Organization).filter_by(place_id=event.place_id, name=org_name).first()
        if not org:
            org = Organization(
                name=org_name, 
                classification="committee", 
                place_id=event.place_id,
                ocd_id=generate_ocd_id('organization')
            )
            session.add(org)
            session.flush()
        
        if event.organization_id != org.id:
            event.organization_id = org.id
            count += 1
            for catalog_id, in (
                session.query(Catalog.id)
                .join(Document, Document.catalog_id == Catalog.id)
                .filter(Document.event_id == event.id)
                .distinct()
                .all()
            ):
                changed_catalog_ids.add(catalog_id)

    session.commit()
    session.close()
    counts = {
        "selected": len(events),
        "linked": count,
        "reindexed": 0,
        "failed_reindex": 0,
    }
    if changed_catalog_ids:
        reindex_summary = reindex_catalogs(changed_catalog_ids)
        counts["reindexed"] = reindex_summary["catalogs_reindexed"]
        counts["failed_reindex"] = reindex_summary["catalogs_failed"]
        print(
            "targeted_reindex_summary "
            f"considered={reindex_summary['catalogs_considered']} "
            f"reindexed={reindex_summary['catalogs_reindexed']} "
            f"failed={reindex_summary['catalogs_failed']}"
        )
    print(f"Backfill complete. Linked {count} events to organizations.")
    return counts


def backfill_organizations():
    return run_organization_backfill()

if __name__ == "__main__":
    backfill_organizations()
