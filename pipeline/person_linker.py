from __future__ import annotations

from pipeline.db_session import db_session
from pipeline.indexer import reindex_catalogs
from pipeline.person_cache import find_best_person_match_cached
from pipeline.person_mutations import create_person_for_event, ensure_official_membership, promote_person_if_official
from pipeline.person_names import has_official_title_context, infer_person_type, normalize_person_name
from pipeline.person_selectors import (
    build_global_exact_people,
    count_people_linking_diagnostics,
    empty_people_linking_counts,
    load_city_person_cache,
    load_membership_cache,
    select_ready_catalog_events,
)
from pipeline.utils import is_likely_human_name


__all__ = [
    "has_official_title_context",
    "infer_person_type",
    "link_people",
    "normalize_person_name",
    "run_people_linking",
]


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

    # Use context manager for automatic session cleanup and error handling.
    with db_session() as session:
        scoped_catalog_ids = None
        if catalog_ids is not None:
            scoped_catalog_ids = sorted({int(cid) for cid in catalog_ids})

        ready_rows = select_ready_catalog_events(session, catalog_ids=scoped_catalog_ids)
        total_ready = len(ready_rows)
        print(f"Processing {total_ready} documents for people...")

        if scoped_catalog_ids == []:
            return empty_people_linking_counts()

        if total_ready == 0:
            # DIAGNOSTIC: Why is it zero? Help developers debug disconnected data.
            diagnostics = count_people_linking_diagnostics(session)
            print(f"DIAGNOSTIC: Catalog with entities: {diagnostics['catalogs_with_entities']}")
            print(f"DIAGNOSTIC: Documents in DB: {diagnostics['documents']}")
            print(f"DIAGNOSTIC: Events in DB: {diagnostics['events']}")
            print("DIAGNOSTIC: If counts are > 0 but ready is 0, the 'joins' are failing (Disconnected data).")

        city_people_cache = {}
        membership_cache = load_membership_cache(session, ready_rows)
        cities_loaded = 0
        exact_matches = 0
        fuzzy_matches = 0
        catalogs_with_people = 0
        global_exact_people = build_global_exact_people(session)

        person_count = 0
        membership_count = 0
        changed_catalog_ids: set[int] = set()

        # Process each document.
        for catalog, event in ready_rows:
            entities = catalog.entities or {}
            people_names = entities.get("persons", [])

            if not people_names:
                continue
            catalogs_with_people += 1

            org_id = event.organization_id
            if not org_id:
                continue

            if event.place_id not in city_people_cache:
                city_people_cache[event.place_id] = load_city_person_cache(session, event.place_id)
                cities_loaded += 1

            for raw_name in people_names:
                name = normalize_person_name(raw_name)
                person_type = infer_person_type(raw_name)

                if not is_likely_human_name(name):
                    continue

                existing_person, match_mode = find_best_person_match_cached(
                    name,
                    city_people_cache[event.place_id],
                    global_exact=global_exact_people,
                )
                if match_mode == "exact":
                    exact_matches += 1
                elif match_mode == "fuzzy":
                    fuzzy_matches += 1

                if not existing_person:
                    existing_person = create_person_for_event(
                        session,
                        name=name,
                        person_type=person_type,
                        event=event,
                        city_cache=city_people_cache[event.place_id],
                        global_exact_people=global_exact_people,
                    )
                    person_count += 1
                    changed_catalog_ids.add(catalog.id)
                elif promote_person_if_official(existing_person, person_type):
                    changed_catalog_ids.add(catalog.id)

                if ensure_official_membership(
                    session,
                    person=existing_person,
                    organization_id=org_id,
                    membership_cache=membership_cache,
                ):
                    membership_count += 1
                    changed_catalog_ids.add(catalog.id)

        session.commit()

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
