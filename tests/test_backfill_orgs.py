from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.backfill_orgs import backfill_organizations
from pipeline.models import Base, Event, Organization, Place


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def test_backfill_creates_default_and_links_events(mocker):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:test")
    session.add(place)
    session.flush()
    session.add_all(
        [
            Event(name="Regular", place_id=place.id, meeting_type="Regular City Council"),
            Event(name="Planning", place_id=place.id, meeting_type="Planning Commission"),
        ]
    )
    session.commit()
    session.close()

    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)
    mocker.patch("pipeline.backfill_orgs.generate_ocd_id", side_effect=["ocd-org/1", "ocd-org/2", "ocd-org/3"])

    backfill_organizations()

    verify = sessionmaker(bind=engine)()
    org_names = {o.name for o in verify.query(Organization).all()}
    assert "City Council" in org_names
    assert "Planning Commission" in org_names
    assert verify.query(Event).filter(Event.organization_id.is_(None)).count() == 0
    verify.close()
    engine.dispose()


def test_backfill_is_idempotent(mocker):
    engine, session = _session()
    place = Place(name="Test City", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:test")
    session.add(place)
    session.flush()
    place_id = place.id
    session.add(Event(name="Parks", place_id=place.id, meeting_type="Parks Committee"))
    session.commit()
    session.close()

    mocker.patch("pipeline.backfill_orgs.db_connect", return_value=engine)
    mocker.patch("pipeline.backfill_orgs.generate_ocd_id", side_effect=[f"ocd-org/{i}" for i in range(1, 10)])

    backfill_organizations()
    backfill_organizations()

    verify = sessionmaker(bind=engine)()
    council_count = verify.query(Organization).filter_by(place_id=place_id, name="City Council").count()
    parks_count = verify.query(Organization).filter_by(place_id=place_id, name="Parks & Recreation Commission").count()
    assert council_count == 1
    assert parks_count == 1
    verify.close()
    engine.dispose()
