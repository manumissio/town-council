import os
import sys
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import db_connect, Place, Organization, Event

def backfill_organizations():
    """
    Migration Script: Populates the new 'organization' table based on existing meetings.
    
    How it works:
    1. It looks at every meeting (Event) we currently have.
    2. It tries to guess the organization name (e.g., "City Council").
    3. It creates an Organization record for that city if it doesn't exist.
    4. It links the Meeting to that Organization.
    """
    print("Connecting to database for organization backfill...")
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    events = session.query(Event).all()
    print(f"Found {len(events)} events to process.")

    org_cache = {} # (place_id, org_name) -> Organization object

    count = 0
    for event in events:
        # Default to "City Council" if we can't determine it, as most pilot data is council meetings.
        org_name = "City Council"
        raw_name = (event.meeting_type or "").lower()
        
        if "planning commission" in raw_name:
            org_name = "Planning Commission"
        elif "parks" in raw_name:
            org_name = "Parks & Recreation Commission"
        
        cache_key = (event.place_id, org_name)
        
        if cache_key not in org_cache:
            # Check if this org already exists in the DB for this city
            org = session.query(Organization).filter_by(
                place_id=event.place_id, 
                name=org_name
            ).first()
            
            if not org:
                print(f"Creating new Organization: '{org_name}' for Place ID {event.place_id}")
                org = Organization(
                    place_id=event.place_id,
                    name=org_name,
                    classification="legislature" if org_name == "City Council" else "committee"
                )
                session.add(org)
                session.flush() # Get the ID immediately
            
            org_cache[cache_key] = org
        
        # Link the event to the organization
        event.organization_id = org_cache[cache_key].id
        count += 1

    session.commit()
    session.close()
    print(f"Backfill complete. Linked {count} events to organizations.")

if __name__ == "__main__":
    backfill_organizations()
