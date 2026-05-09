from __future__ import annotations

from pipeline.models import Catalog, Document, Event, Membership, Organization, Person
from pipeline.person_cache import build_city_person_cache, normalized_name_key
from pipeline.profiling import apply_catalog_id_scope


def empty_people_linking_counts():
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


def select_ready_catalog_events(session, catalog_ids=None):
    query = (
        session.query(Catalog, Event)
        .join(Document, Catalog.id == Document.catalog_id)
        .join(Event, Document.event_id == Event.id)
        .filter(Catalog.entities != None)
    )
    if catalog_ids is not None:
        scoped_catalog_ids = sorted({int(cid) for cid in catalog_ids})
        if not scoped_catalog_ids:
            return []
        query = query.filter(Catalog.id.in_(scoped_catalog_ids))
    query = apply_catalog_id_scope(query, Catalog.id)
    return query.all()


def count_people_linking_diagnostics(session):
    return {
        "catalogs_with_entities": session.query(Catalog).filter(Catalog.entities != None).count(),
        "documents": session.query(Document).count(),
        "events": session.query(Event).count(),
    }


def build_global_exact_people(session):
    return {normalized_name_key(person.name): person for person in session.query(Person).all()}


def load_membership_cache(session, ready_rows):
    organization_ids = sorted({int(event.organization_id) for _catalog, event in ready_rows if event.organization_id})
    if not organization_ids:
        return set()
    return {
        (int(person_id), int(organization_id))
        for person_id, organization_id in session.query(Membership.person_id, Membership.organization_id)
        .filter(Membership.organization_id.in_(organization_ids))
        .all()
    }


def load_city_person_cache(session, place_id):
    city_people = session.query(Person).join(Membership).join(Organization).filter(Organization.place_id == place_id).all()
    return build_city_person_cache(city_people)
