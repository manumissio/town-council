from contextlib import contextmanager
from unittest.mock import MagicMock

from pipeline import person_linker
from pipeline.models import Place, Organization, Event, Catalog, Document, Person, Membership


def test_link_people_keeps_mention_without_membership(db_session, monkeypatch):
    @contextmanager
    def fake_db_session():
        yield db_session

    monkeypatch.setattr(person_linker, "db_session", fake_db_session)
    reindex_spy = MagicMock(return_value={"catalogs_considered": 1, "catalogs_reindexed": 1, "catalogs_failed": 0})
    monkeypatch.setattr(person_linker, "reindex_catalogs", reindex_spy)

    place = Place(name="Berkeley", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:berkeley")
    db_session.add(place)
    db_session.flush()
    org = Organization(name="City Council", place_id=place.id)
    db_session.add(org)
    db_session.flush()
    event = Event(name="Regular Meeting", place_id=place.id, organization_id=org.id, ocd_division_id=place.ocd_division_id)
    db_session.add(event)
    db_session.flush()

    catalog = Catalog(url_hash="mention_hash", filename="m.pdf", entities={"persons": ["Jesse Arreguin"]})
    db_session.add(catalog)
    db_session.flush()
    db_session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id))
    db_session.commit()

    person_linker.link_people()

    person = db_session.query(Person).filter(Person.name == "Jesse Arreguin").first()
    assert person is not None
    assert person.person_type == "mentioned"
    assert db_session.query(Membership).count() == 0
    reindex_spy.assert_called_once_with({catalog.id})


def test_link_people_promotes_official_with_membership(db_session, monkeypatch):
    @contextmanager
    def fake_db_session():
        yield db_session

    monkeypatch.setattr(person_linker, "db_session", fake_db_session)
    reindex_spy = MagicMock(return_value={"catalogs_considered": 1, "catalogs_reindexed": 1, "catalogs_failed": 0})
    monkeypatch.setattr(person_linker, "reindex_catalogs", reindex_spy)

    place = Place(name="Berkeley", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:berkeley")
    db_session.add(place)
    db_session.flush()
    org = Organization(name="City Council", place_id=place.id)
    db_session.add(org)
    db_session.flush()
    event = Event(name="Regular Meeting", place_id=place.id, organization_id=org.id, ocd_division_id=place.ocd_division_id)
    db_session.add(event)
    db_session.flush()

    catalog = Catalog(url_hash="official_hash", filename="o.pdf", entities={"persons": ["Mayor Jesse Arreguin"]})
    db_session.add(catalog)
    db_session.flush()
    db_session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id))
    db_session.commit()

    person_linker.link_people()

    person = db_session.query(Person).filter(Person.name == "Jesse Arreguin").first()
    assert person is not None
    assert person.person_type == "official"
    assert db_session.query(Membership).count() == 1
    reindex_spy.assert_called_once_with({catalog.id})
