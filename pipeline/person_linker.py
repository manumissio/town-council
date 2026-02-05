import os
import sys
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import db_connect, Catalog, Document, Event, Organization, Person, Membership

def link_people():
    """
    Intelligence Worker: Promotes raw text names to structured Person & Membership records.
    
    How it works for a developer:
    1. It looks at the AI-extracted names in the 'Catalog' (the entities JSON).
    2. It finds which Meeting (Event) and Body (Organization) that document belongs to.
    3. It creates a unique 'Person' record if one doesn't exist for that name.
    4. It creates a 'Membership' record linking the person to the legislative body.
    """
    print("Connecting to database for People & Membership linking...")
    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find all documents that have NLP entities (people names)
    # We join Document and Event to know WHICH Organization to link them to.
    query = session.query(Catalog, Event).join(
        Document, Catalog.id == Document.catalog_id
    ).join(
        Event, Document.event_id == Event.id
    ).filter(Catalog.entities != None)

    print(f"Processing {query.count()} documents for people...")

    person_cache = {} # (city_id, name.lower()) -> Person ID
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
            continue # Skip if we don't know the body

        for raw_name in people_names:
            # Basic cleanup: Remove titles and extra whitespace
            name = raw_name.replace("Mayor ", "").replace("Councilmember ", "").strip()
            if len(name) < 3 or " " not in name:
                continue # Skip suspicious or single-word names (likely errors)

            name_key = (event.place_id, name.lower())

            # 1. Find or Create Person
            if name_key not in person_cache:
                # Check DB first
                person = session.query(Person).filter(func.lower(Person.name) == name.lower()).first()
                if not person:
                    person = Person(name=name, current_role=f"Official in {event.place.name}")
                    session.add(person)
                    session.flush()
                    person_count += 1
                person_cache[name_key] = person.id
            
            person_id = person_cache[name_key]

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

if __name__ == "__main__":
    link_people()
