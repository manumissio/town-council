import io

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Place
from pipeline.seed_places import seed_places


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_seed_places_inserts_and_updates_rows(mocker):
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

    mocker.patch("pipeline.seed_places.db_connect", return_value=engine)
    mocker.patch("pipeline.seed_places.create_tables")
    mocker.patch("pipeline.seed_places.os.path.exists", return_value=True)
    mocker.patch("builtins.open", return_value=io.StringIO(csv_text))

    seed_places()

    verify = Session()
    existing = verify.query(Place).filter_by(ocd_division_id="ocd-division/country:us/state:ca/place:existing").one()
    new = verify.query(Place).filter_by(ocd_division_id="ocd-division/country:us/state:ca/place:newville").one()
    assert existing.seed_url == "https://new.example.com"
    assert existing.hosting_service == "updated"
    assert new.name == "Newville"
    verify.close()
    engine.dispose()


def test_seed_places_rolls_back_on_commit_error(mocker):
    fake_session = mocker.MagicMock()
    fake_session.commit.side_effect = ValueError("bad csv")
    fake_session.query.return_value.filter.return_value.first.return_value = None

    mocker.patch("pipeline.seed_places.db_connect", return_value=object())
    mocker.patch("pipeline.seed_places.create_tables")
    mocker.patch("pipeline.seed_places.sessionmaker", return_value=lambda: fake_session)
    mocker.patch("pipeline.seed_places.os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        return_value=io.StringIO(
            "city,state,country,display_name,ocd_division_id,city_council_url,hosting_services\n"
            "Bad,CA,us,Bad City,ocd-division/country:us/state:ca/place:bad,https://bad.example.com,host\n"
        ),
    )

    seed_places()

    fake_session.rollback.assert_called_once()
    fake_session.close.assert_called_once()
