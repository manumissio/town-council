import os
import sys
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import db_connect, Place, Organization, Event
from pipeline.utils import generate_ocd_id

def backfill_organizations():
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

    # 1. Ensure 'City Council' exists for EVERY city
    places = session.query(Place).all()
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
    events = session.query(Event).all()
    print(f"Found {len(events)} events to process.")

    count = 0
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
        
        event.organization_id = org.id
        count += 1

    session.commit()
    session.close()
    print(f"Backfill complete. Linked {count} events to organizations.")

if __name__ == "__main__":
    backfill_organizations()
