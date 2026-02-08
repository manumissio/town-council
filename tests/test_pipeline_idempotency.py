import datetime

from pipeline.models import Catalog, Document, Event, EventStage, Membership, Organization, Person, Place
from pipeline.person_linker import link_people
from pipeline.promote_stage import promote_stage


def test_promote_stage_is_idempotent_for_same_event(db_session):
    place = Place(
        name="Idempotent City",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:idempotent",
    )
    db_session.add(place)
    db_session.flush()

    db_session.add(
        EventStage(
            ocd_division_id=place.ocd_division_id,
            name="Regular Meeting",
            record_date=datetime.date(2026, 2, 2),
            source="crawler",
            source_url="https://example.com/regular",
            meeting_type="Regular",
        )
    )
    db_session.commit()

    promote_stage()
    promote_stage()

    assert db_session.query(Event).filter_by(name="Regular Meeting").count() == 1


def test_link_people_is_idempotent_for_person_and_membership(db_session):
    place = Place(
        name="People City",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:people",
    )
    db_session.add(place)
    db_session.flush()

    org = Organization(name="City Council", classification="legislature", place_id=place.id, ocd_id="ocd-organization/people")
    db_session.add(org)
    db_session.flush()

    event = Event(
        name="Regular Meeting",
        place_id=place.id,
        organization_id=org.id,
        record_date=datetime.date(2026, 2, 3),
        source="crawler",
        source_url="https://example.com/regular",
        meeting_type="Regular",
        ocd_id="ocd-event/people",
    )
    db_session.add(event)
    db_session.flush()

    catalog = Catalog(url_hash="people-hash", filename="people.pdf", entities={"persons": ["Mayor Pat Lee"]})
    db_session.add(catalog)
    db_session.flush()
    db_session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id, url_hash="doc-people"))
    db_session.commit()

    link_people()
    link_people()

    person_count = db_session.query(Person).filter_by(name="Pat Lee").count()
    membership_count = (
        db_session.query(Membership)
        .join(Person, Membership.person_id == Person.id)
        .filter(Person.name == "Pat Lee", Membership.organization_id == org.id)
        .count()
    )

    assert person_count == 1
    assert membership_count == 1
