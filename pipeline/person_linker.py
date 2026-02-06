import os
import sys
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import db_connect, Catalog, Document, Event, Organization, Person, Membership
from pipeline.utils import generate_ocd_id, find_best_person_match

def link_people():
    """
    Intelligence Worker: Promotes raw text names to structured Person & Membership records.
    
    How it works for a developer:
    1. It looks at the AI-extracted names in the 'Catalog' (the entities JSON).
    2. It finds which Meeting (Event) and Body (Organization) that document belongs to.
    3. It uses Traditional AI (Fuzzy Matching) to see if this person already exists.
    4. It creates a unique 'Person' record if no close match is found.
    5. It creates a 'Membership' record linking the person to the legislative body.
    """
    print("Connecting to database for People & Membership linking...")
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find all documents that have NLP entities (people names)
    query = session.query(Catalog, Event).join(
        Document, Catalog.id == Document.catalog_id
    ).join(
        Event, Document.event_id == Event.id
    ).filter(Catalog.entities != None)

    print(f"Processing {query.count()} documents for people...")

    # Performance: Pre-fetch all people grouped by city (Blocking)
    # This prevents the "O(N^2)" problem where matching gets slower as the DB grows.
    city_people_cache = {} # city_id -> list of Person objects
    membership_cache = set() # (person_id, org_id)

    person_count = 0
    membership_count = 0

    for catalog, event in query:
        entities = catalog.entities or {}
        people_names = entities.get('persons', [])
        
        if not people_names:
            continue

        # We need the organization for this event
        org_id = event.organization_id
        if not org_id:
            continue 

        # BLOCKING: Ensure we have the list of people for THIS city only.
        # We don't compare a Berkeley official against a Belmont official.
        if event.place_id not in city_people_cache:
            # We fetch all people who have at least one membership in any organization in this city
            city_people = session.query(Person).join(Membership).join(Organization).filter(
                Organization.place_id == event.place_id
            ).all()
            city_people_cache[event.place_id] = city_people

        for raw_name in people_names:
            # Basic cleanup: Remove titles and extra whitespace
            name = raw_name.replace("Mayor ", "").replace("Councilmember ", "").strip()
            if len(name) < 3 or " " not in name:
                continue 

            # 1. Fuzzy Entity Resolution
            # Check if this name is "close enough" to someone we already know in this city.
            existing_person = find_best_person_match(name, city_people_cache[event.place_id])
            
            if not existing_person:
                # No fuzzy match? Create a new person.
                existing_person = Person(
                    name=name, 
                    current_role=f"Official in {event.place.name}",
                    ocd_id=generate_ocd_id('person')
                )
                session.add(existing_person)
                session.flush()
                # Update our blocking cache immediately so the next doc can find them
                city_people_cache[event.place_id].append(existing_person)
                person_count += 1
            
            person_id = existing_person.id

            # 2. Find or Create Membership
            mem_key = (person_id, org_id)
            if mem_key not in membership_cache:
                # Check DB first
                exists = session.query(Membership).filter_by(person_id=person_id, organization_id=org_id).first()
                if not exists:
                    membership = Membership(
                        person_id=person_id, 
                        organization_id=org_id,
                        label="Member",
                        role="member"
                    )
                    session.add(membership)
                    membership_count += 1
                membership_cache.add(mem_key)

    session.commit()
    session.close()
    print(f"Linking complete. Created {person_count} new People and {membership_count} new Memberships.")

    session.commit()
    session.close()
    print(f"Linking complete. Created {person_count} new People and {membership_count} new Memberships.")

if __name__ == "__main__":
    link_people()
