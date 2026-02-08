import os
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.modules["llama_cpp"] = MagicMock()

from api.main import app, get_db  # noqa: E402
from pipeline.models import Base, Person  # noqa: E402


def _build_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_people_endpoint_defaults_to_officials_only():
    Session = _build_db()
    seed_db = Session()
    seed_db.add_all([
        Person(name="Official One", ocd_id="ocd-person/00000000-0000-0000-0000-000000000001", person_type="official"),
        Person(name="Mention One", ocd_id="ocd-person/00000000-0000-0000-0000-000000000002", person_type="mentioned"),
    ])
    seed_db.commit()
    seed_db.close()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        response = client.get("/people")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["results"][0]["name"] == "Official One"
    finally:
        del app.dependency_overrides[get_db]


def test_people_endpoint_include_mentions_true_returns_all():
    Session = _build_db()
    seed_db = Session()
    seed_db.add_all([
        Person(name="Official One", ocd_id="ocd-person/00000000-0000-0000-0000-000000000011", person_type="official"),
        Person(name="Mention One", ocd_id="ocd-person/00000000-0000-0000-0000-000000000012", person_type="mentioned"),
    ])
    seed_db.commit()
    seed_db.close()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        response = client.get("/people?include_mentions=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert {row["name"] for row in data["results"]} == {"Official One", "Mention One"}
    finally:
        del app.dependency_overrides[get_db]
