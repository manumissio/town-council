import datetime

from pipeline.models import Event, EventStage, Place
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
