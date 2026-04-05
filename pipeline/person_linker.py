from rapidfuzz import fuzz, process

from pipeline.models import Catalog, Document, Event, Organization, Person, Membership
from pipeline.db_session import db_session
from pipeline.indexer import reindex_catalogs
from pipeline.profiling import apply_catalog_id_scope
from pipeline.utils import generate_ocd_id, is_likely_human_name

OFFICIAL_TITLE_PREFIXES = (
    "Mayor ",
    "Councilmember ",
    "Vice Mayor ",
    "Chair ",
    "Commissioner ",
)


def has_official_title_context(raw_name):
    """
    Returns True when the extracted string includes an official title prefix.
    """
    value = (raw_name or "").strip().lower()
    return any(value.startswith(prefix.lower()) for prefix in OFFICIAL_TITLE_PREFIXES)


def normalize_person_name(raw_name):
    """
    Removes role prefixes and normalizes whitespace before matching/saving.
    """
    name = (raw_name or "").strip()
    prefixes = [
        "Mayor ", "Councilmember ", "Vice Mayor ", "Chair ", "Director ",
        "Commissioner ", "Moved by ", "Seconded by ", "Ayes: ", "Noes: ",
        "Ayes : ", "Noes : ", "Ayes:  ", "Noes:  "
    ]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
    return name


def infer_person_type(raw_name):
    """
    Simple classification gate:
    - Official when strong title context is present
    - Mentioned otherwise
    """
    return "official" if has_official_title_context(raw_name) else "mentioned"


def _normalized_name_key(name):
    return " ".join((name or "").strip().split()).casefold()


def _build_city_person_cache(people):
    exact = {}
    fuzzy_choices = []
    fuzzy_map = {}
    for person in people:
        exact[_normalized_name_key(person.name)] = person
        fuzzy_choices.append(person.name)
        fuzzy_map[person.name] = person
    return {
        "people": list(people),
        "exact": exact,
        "fuzzy_choices": fuzzy_choices,
        "fuzzy_map": fuzzy_map,
    }


def _find_best_person_match_cached(name, cache, *, global_exact=None, threshold=85):
    exact_match = cache["exact"].get(_normalized_name_key(name))
    if exact_match is not None:
        return exact_match, "exact"
    if global_exact is not None:
        exact_match = global_exact.get(_normalized_name_key(name))
        if exact_match is not None:
            return exact_match, "exact"

    if not cache["fuzzy_choices"]:
        return None, None

    result = process.extractOne(name, cache["fuzzy_choices"], scorer=fuzz.token_sort_ratio)
    if result:
        match_name, score, _index = result
        if score >= threshold:
            return cache["fuzzy_map"][match_name], "fuzzy"
    return None, None


def run_people_linking(catalog_ids=None):
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
        if catalog_ids is not None:
            scoped_catalog_ids = sorted({int(cid) for cid in catalog_ids})
            if not scoped_catalog_ids:
                print("Processing 0 documents for people...")
                return {
                    "selected": 0,
                    "catalogs_with_people": 0,
                    "catalogs_changed": 0,
                    "people_created": 0,
                    "memberships_created": 0,
                    "exact_matches": 0,
                    "fuzzy_matches": 0,
                    "cities_loaded": 0,
                    "reindexed": 0,
                    "failed_reindex": 0,
                }
            query = query.filter(Catalog.id.in_(scoped_catalog_ids))
        query = apply_catalog_id_scope(query, Catalog.id)
        ready_rows = query.all()
        total_ready = len(ready_rows)
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
        cities_loaded = 0
        exact_matches = 0
        fuzzy_matches = 0
        catalogs_with_people = 0
        global_exact_people = {
            _normalized_name_key(person.name): person
            for person in session.query(Person).all()
        }

        person_count = 0
        membership_count = 0
        changed_catalog_ids: set[int] = set()
        organization_ids = sorted({int(event.organization_id) for _catalog, event in ready_rows if event.organization_id})
        if organization_ids:
            membership_cache = {
                (int(person_id), int(organization_id))
                for person_id, organization_id in session.query(Membership.person_id, Membership.organization_id)
                .filter(Membership.organization_id.in_(organization_ids))
                .all()
            }

        # Process each document
        for catalog, event in ready_rows:
            # Extract the list of person names from the entities JSON
            entities = catalog.entities or {}
            people_names = entities.get('persons', [])

            if not people_names:
                continue
            catalogs_with_people += 1

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
                city_people_cache[event.place_id] = _build_city_person_cache(city_people)
                cities_loaded += 1

            # Process each extracted name
            for raw_name in people_names:
                # Normalize extracted names once so filtering/matching stays deterministic.
                name = normalize_person_name(raw_name)
                person_type = infer_person_type(raw_name)

                # QUALITY CONTROL: Ensure this string is actually a human name
                # Filters out things like "City Staff", "Item 5", etc.
                if not is_likely_human_name(name):
                    continue

                # 1. Fuzzy Entity Resolution
                # Check if this name is "close enough" to someone we already know
                # Uses Levenshtein distance to handle variations in spelling
                existing_person, match_mode = _find_best_person_match_cached(
                    name,
                    city_people_cache[event.place_id],
                    global_exact=global_exact_people,
                )
                if match_mode == "exact":
                    exact_matches += 1
                elif match_mode == "fuzzy":
                    fuzzy_matches += 1

                if not existing_person:
                    # No fuzzy match? This is a new person we haven't seen before
                    role_label = (
                        f"Official in {event.place.name}"
                        if person_type == "official"
                        else f"Mentioned in {event.place.name} records"
                    )
                    existing_person = Person(
                        name=name,
                        current_role=role_label,
                        ocd_id=generate_ocd_id('person'),
                        person_type=person_type
                    )
                    session.add(existing_person)
                    session.flush()  # Get the ID immediately
                    # Update our blocking cache so the next doc can find them
                    city_people_cache[event.place_id]["people"].append(existing_person)
                    city_people_cache[event.place_id]["exact"][_normalized_name_key(existing_person.name)] = existing_person
                    city_people_cache[event.place_id]["fuzzy_choices"].append(existing_person.name)
                    city_people_cache[event.place_id]["fuzzy_map"][existing_person.name] = existing_person
                    global_exact_people[_normalized_name_key(existing_person.name)] = existing_person
                    person_count += 1
                    changed_catalog_ids.add(catalog.id)
                elif person_type == "official" and existing_person.person_type != "official":
                    # Upgrade mention-only profiles when we later see official evidence.
                    existing_person.person_type = "official"
                    changed_catalog_ids.add(catalog.id)

                person_id = existing_person.id

                # 2. Find or Create Membership for official profiles only.
                # Mention-only rows keep identity info but are not treated as body members.
                if existing_person.person_type != "official":
                    continue

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
                        changed_catalog_ids.add(catalog.id)
                    # Cache it to avoid duplicate checks
                    membership_cache.add(mem_key)

        # Save all the new people and memberships to the database
        # The context manager will automatically rollback if this fails
        session.commit()

        # Print summary of what we accomplished
        print(f"Linking complete. Created {person_count} new People and {membership_count} new Memberships.")
        counts = {
            "selected": total_ready,
            "catalogs_with_people": catalogs_with_people,
            "catalogs_changed": len(changed_catalog_ids),
            "people_created": person_count,
            "memberships_created": membership_count,
            "exact_matches": exact_matches,
            "fuzzy_matches": fuzzy_matches,
            "cities_loaded": cities_loaded,
            "reindexed": 0,
            "failed_reindex": 0,
        }
        print(
            "people_linking "
            f"selected={counts['selected']} "
            f"catalogs_with_people={counts['catalogs_with_people']} "
            f"catalogs_changed={counts['catalogs_changed']} "
            f"people_created={counts['people_created']} "
            f"memberships_created={counts['memberships_created']} "
            f"exact_matches={counts['exact_matches']} "
            f"fuzzy_matches={counts['fuzzy_matches']} "
            f"cities_loaded={counts['cities_loaded']}"
        )
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
        return counts


def link_people(catalog_ids=None):
    return run_people_linking(catalog_ids=catalog_ids)

if __name__ == "__main__":
    link_people()
