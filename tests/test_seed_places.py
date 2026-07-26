import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Place
from pipeline.seed_places import seed_places


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_seed_places_inserts_and_updates_rows(mocker, tmp_path):
    engine = _engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(
        Place(
            name="Existing",
            state="CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:existing",
            seed_url="https://old.example.com",
            hosting_service="legacy",
        )
    )
    session.commit()
    session.close()

    csv_text = (
        "city,state,country,display_name,ocd_division_id,city_council_url,hosting_services\n"
        "Existing,CA,us,Existing City,ocd-division/country:us/state:ca/place:existing,https://new.example.com,updated\n"
        "Newville,CA,us,Newville City,ocd-division/country:us/state:ca/place:newville,https://newville.example.com,granicus\n"
    )

    city_metadata_path = tmp_path / "cities.csv"
    city_metadata_path.write_text(csv_text, encoding="utf-8")
    mocker.patch("pipeline.seed_places.db_connect", return_value=engine)
    mocker.patch("pipeline.seed_places.CITY_METADATA_PATH", city_metadata_path)

    seed_places()

    verify = Session()
    existing = verify.query(Place).filter_by(ocd_division_id="ocd-division/country:us/state:ca/place:existing").one()
    new = verify.query(Place).filter_by(ocd_division_id="ocd-division/country:us/state:ca/place:newville").one()
    assert existing.seed_url == "https://new.example.com"
    assert existing.hosting_service == "updated"
    assert new.name == "Newville"
    verify.close()
    engine.dispose()


def test_seed_places_rolls_back_on_commit_error(mocker, tmp_path):
    fake_session = mocker.MagicMock()
    fake_session.commit.side_effect = ValueError("bad csv")
    fake_session.query.return_value.filter.return_value.first.return_value = None
    rollback_observed = False

    def record_rollback() -> None:
        nonlocal rollback_observed
        rollback_observed = True

    mocker.patch("pipeline.seed_places.db_connect", return_value=object())
    mocker.patch("pipeline.seed_places.sessionmaker", return_value=lambda: fake_session)
    fake_session.rollback.side_effect = record_rollback
    city_metadata_path = tmp_path / "cities.csv"
    city_metadata_path.write_text(
        "city,state,country,display_name,ocd_division_id,city_council_url,hosting_services\n"
        "Bad,CA,us,Bad City,ocd-division/country:us/state:ca/place:bad,https://bad.example.com,host\n",
        encoding="utf-8",
    )
    mocker.patch("pipeline.seed_places.CITY_METADATA_PATH", city_metadata_path)

    with pytest.raises(ValueError, match="bad csv"):
        seed_places()

    assert rollback_observed is True


def test_seed_places_fails_on_unmigrated_schema(mocker, caplog):
    engine = create_engine("sqlite:///:memory:")
    rollback_observed = False

    def record_rollback(_connection) -> None:
        nonlocal rollback_observed
        rollback_observed = True

    event.listen(engine, "rollback", record_rollback)
    mocker.patch("pipeline.seed_places.db_connect", return_value=engine)

    with pytest.raises(OperationalError):
        seed_places()

    assert rollback_observed is True
    assert "Error during seeding" in caplog.text
    engine.dispose()
