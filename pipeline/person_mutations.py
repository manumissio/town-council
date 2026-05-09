from __future__ import annotations

from pipeline.models import Membership, Person
from pipeline.person_cache import add_person_to_city_cache, normalized_name_key
from pipeline.utils_ocd import generate_ocd_id


def create_person_for_event(session, *, name, person_type, event, city_cache, global_exact_people):
    role_label = (
        f"Official in {event.place.name}"
        if person_type == "official"
        else f"Mentioned in {event.place.name} records"
    )
    person = Person(
        name=name,
        current_role=role_label,
        ocd_id=generate_ocd_id("person"),
        person_type=person_type,
    )
    session.add(person)
    session.flush()
    add_person_to_city_cache(city_cache, person)
    global_exact_people[normalized_name_key(person.name)] = person
    return person


def promote_person_if_official(person, person_type):
    if person_type == "official" and person.person_type != "official":
        person.person_type = "official"
        return True
    return False


def ensure_official_membership(session, *, person, organization_id, membership_cache):
    if person.person_type != "official":
        return False

    mem_key = (person.id, organization_id)
    if mem_key in membership_cache:
        return False

    exists = session.query(Membership).filter_by(person_id=person.id, organization_id=organization_id).first()
    if exists:
        membership_cache.add(mem_key)
        return False

    membership = Membership(
        person_id=person.id,
        organization_id=organization_id,
        label="Member",
        role="member",
    )
    session.add(membership)
    membership_cache.add(mem_key)
    return True
