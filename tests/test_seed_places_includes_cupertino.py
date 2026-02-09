from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Place
from pipeline.seed_places import seed_places


def test_seed_places_includes_cupertino_from_repo_csv(mocker):
    """
    Contract test: the repo's canonical city list includes Cupertino and seeding
    creates/updates a Place row for it.

    Why this matters:
    If Cupertino disappears from the seed list (or changes shape), the crawler can
    still "run" but the rest of the pipeline won't know how to associate meetings
    with a Place.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # Force seed_places() to use our in-memory DB, but read the real CSV from the repo.
    mocker.patch("pipeline.seed_places.db_connect", return_value=engine)
    mocker.patch("pipeline.seed_places.create_tables")  # tables already exist
    mocker.patch("pipeline.seed_places.os.path.exists", return_value=True)

    seed_places()

    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        place = (
            db.query(Place)
            .filter_by(ocd_division_id="ocd-division/country:us/state:ca/place:cupertino")
            .one()
        )
        assert place.display_name == "ca_cupertino"
        assert place.crawler_name == "cupertino"
        assert (place.seed_url or "").startswith("https://cupertino.legistar.com/")
        assert "legistar" in (place.hosting_service or "")
    finally:
        db.close()
        engine.dispose()

