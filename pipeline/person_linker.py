import os
import sys
from sqlalchemy import func

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import Catalog, Document, Event, Organization, Person, Membership
from pipeline.db_session import db_session
from pipeline.utils import generate_ocd_id, find_best_person_match, is_likely_human_name

def link_people():
    """
    Intelligence Worker: Promotes raw text names to structured Person & Membership records.

    What this does:
    1. Reads AI-extracted names from the 'Catalog' (the entities JSON)
    2. Finds which Meeting (Event) and Legislative Body (Organization) each document belongs to
    3. Uses Fuzzy Matching to check if this person already exists in our database
    4. Creates a unique 'Person' record if no close match is found
    5. Creates a 'Membership' record linking the person to the legislative body

    Why is this needed?
    The NLP worker extracts names like "Mayor Jesse Arreguin" as raw strings.
    This worker converts those strings into:
    - A Person record (Jesse Arreguin, id=123)
    - A Membership record (Jesse Arreguin is a member of Berkeley City Council)

    What is Fuzzy Matching?
    Names appear in different forms: "Jesse Arreguin", "J. Arreguin", "Arreguin, Jesse"
    Fuzzy matching uses string similarity algorithms (Levenshtein distance) to detect
    that these are probably the same person, preventing duplicates.

    What is the "Blocking" optimization?
    Without blocking: Compare each name against ALL people in database (slow!)
    With blocking: Only compare against people from the SAME city (fast!)
    Berkeley has 9 officials, not 10,000. This makes matching O(N) instead of O(N²).
    """
    print("Connecting to database for People & Membership linking...")

    # Use context manager for automatic session cleanup and error handling
    with db_session() as session:
        # Find all documents that have NLP entities (people names)
        # We use joins to find which Event and Organization the document belongs to
        query = session.query(Catalog, Event).join(
            Document, Catalog.id == Document.catalog_id
        ).join(
            Event, Document.event_id == Event.id
        ).filter(Catalog.entities != None)

        total_ready = query.count()
        print(f"Processing {total_ready} documents for people...")

        if total_ready == 0:
            # DIAGNOSTIC: Why is it zero? Help developers debug disconnected data
            cat_count = session.query(Catalog).filter(Catalog.entities != None).count()
            doc_count = session.query(Document).count()
            event_count = session.query(Event).count()
            print(f"DIAGNOSTIC: Catalog with entities: {cat_count}")
            print(f"DIAGNOSTIC: Documents in DB: {doc_count}")
            print(f"DIAGNOSTIC: Events in DB: {event_count}")
            print("DIAGNOSTIC: If counts are > 0 but ready is 0, the 'joins' are failing (Disconnected data).")

        # Performance optimization: Pre-fetch all people grouped by city (Blocking)
        # This prevents the "O(N^2)" problem where matching gets slower as the DB grows
        # city_people_cache: Maps city_id -> list of Person objects in that city
        # membership_cache: Tracks which (person, organization) pairs we've seen
        city_people_cache = {}
        membership_cache = set()

        person_count = 0
        membership_count = 0

        # Process each document
        for catalog, event in query:
            # Extract the list of person names from the entities JSON
            entities = catalog.entities or {}
            people_names = entities.get('persons', [])

            if not people_names:
                continue

            # We need the organization (legislative body) for this event
            org_id = event.organization_id
            if not org_id:
                continue

            # BLOCKING: Ensure we have the list of people for THIS city only
            # Why? We don't want to compare a Berkeley official against a Belmont official
            # This dramatically speeds up fuzzy matching
            if event.place_id not in city_people_cache:
                # Fetch all people who have at least one membership in any org in this city
                city_people = session.query(Person).join(Membership).join(Organization).filter(
                    Organization.place_id == event.place_id
                ).all()
                city_people_cache[event.place_id] = city_people

            # Process each extracted name
            for raw_name in people_names:
                # Basic cleanup: Remove titles and extra whitespace
                name = raw_name.strip()

                # Remove common prefixes found in meeting documents
                # Example: "Mayor Jesse Arreguin" becomes "Jesse Arreguin"
                prefixes = [
                    "Mayor ", "Councilmember ", "Vice Mayor ", "Chair ", "Director ",
                    "Commissioner ", "Moved by ", "Seconded by ", "Ayes: ", "Noes: ",
                    "Ayes : ", "Noes : ", "Ayes:  ", "Noes:  "
                ]
                for prefix in prefixes:
                    if name.startswith(prefix):
                        name = name[len(prefix):].strip()

                # QUALITY CONTROL: Ensure this string is actually a human name
                # Filters out things like "City Staff", "Item 5", etc.
                if not is_likely_human_name(name):
                    continue

                # 1. Fuzzy Entity Resolution
                # Check if this name is "close enough" to someone we already know
                # Uses Levenshtein distance to handle variations in spelling
                existing_person = find_best_person_match(name, city_people_cache[event.place_id])

                if not existing_person:
                    # No fuzzy match? This is a new person we haven't seen before
                    existing_person = Person(
                        name=name,
                        current_role=f"Official in {event.place.name}",
                        ocd_id=generate_ocd_id('person')
                    )
                    session.add(existing_person)
                    session.flush()  # Get the ID immediately
                    # Update our blocking cache so the next doc can find them
                    city_people_cache[event.place_id].append(existing_person)
                    person_count += 1

                person_id = existing_person.id

                # 2. Find or Create Membership
                # A person can be a member of multiple organizations
                # Example: Someone might serve on both City Council and Planning Commission
                mem_key = (person_id, org_id)
                if mem_key not in membership_cache:
                    # Check if this membership already exists in the database
                    exists = session.query(Membership).filter_by(person_id=person_id, organization_id=org_id).first()
                    if not exists:
                        # Create new membership
                        membership = Membership(
                            person_id=person_id,
                            organization_id=org_id,
                            label="Member",
                            role="member"
                        )
                        session.add(membership)
                        membership_count += 1
                    # Cache it to avoid duplicate checks
                    membership_cache.add(mem_key)

        # Save all the new people and memberships to the database
        # The context manager will automatically rollback if this fails
        session.commit()

        # Print summary of what we accomplished
        print(f"Linking complete. Created {person_count} new People and {membership_count} new Memberships.")

if __name__ == "__main__":
    link_people()
