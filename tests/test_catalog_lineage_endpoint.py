from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker
from sqlalchemy.pool import StaticPool
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.lineage_routes import build_lineage_router
from pipeline.models import Base, Catalog, Document, Event, Place


def _get_db():
    raise AssertionError("Test must override the database dependency")


def _lineage_client(db: SQLAlchemySession | MagicMock) -> TestClient:
    limiter = Limiter(key_func=get_remote_address)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(build_lineage_router(limiter=limiter, get_db_dependency=_get_db))

    def override_db():
        yield db

    app.dependency_overrides[_get_db] = override_db
    return TestClient(app)


def test_catalog_lineage_endpoint_returns_thread():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=101, lineage_id="lin-101", lineage_confidence=0.8)
    rows = [
        (
            SimpleNamespace(id=101, lineage_confidence=0.8),
            SimpleNamespace(),
            SimpleNamespace(name="Meeting A", record_date=SimpleNamespace(isoformat=lambda: "2025-01-10")),
            SimpleNamespace(display_name="Berkeley", name="Berkeley"),
        ),
        (
            SimpleNamespace(id=102, lineage_confidence=0.7),
            SimpleNamespace(),
            SimpleNamespace(name="Meeting B", record_date=SimpleNamespace(isoformat=lambda: "2025-02-10")),
            SimpleNamespace(display_name="Berkeley", name="Berkeley"),
        ),
    ]
    lineage_query = db.query.return_value.join.return_value.join.return_value.join.return_value
    lineage_query.filter.return_value.order_by.return_value.all.return_value = rows

    response = _lineage_client(db).get("/catalog/101/lineage")

    assert response.status_code == 200
    lineage = response.json()
    assert lineage["lineage_id"] == "lin-101"
    assert lineage["count"] == 2
    assert [meeting["catalog_id"] for meeting in lineage["meetings"]] == [101, 102]


def test_catalog_lineage_endpoint_applies_minimum_confidence():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    lineage_session = sessionmaker(bind=engine)()
    place = Place(
        id=1,
        name="berkeley",
        display_name="Berkeley",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:berkeley",
    )
    events = [
        Event(id=1, place_id=1, name="Meeting A", record_date=date(2025, 1, 10)),
        Event(id=2, place_id=1, name="Meeting B", record_date=date(2025, 2, 10)),
    ]
    catalogs = [
        Catalog(id=101, url_hash="catalog-101", lineage_id="lin-101", lineage_confidence=0.8),
        Catalog(id=102, url_hash="catalog-102", lineage_id="lin-101", lineage_confidence=0.7),
    ]
    documents = [
        Document(id=1, place_id=1, event_id=1, catalog_id=101),
        Document(id=2, place_id=1, event_id=2, catalog_id=102),
    ]
    lineage_session.add_all([place, *events, *catalogs, *documents])
    lineage_session.commit()
    try:
        response = _lineage_client(lineage_session).get(
            "/catalog/101/lineage?min_confidence=0.75"
        )

        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert [meeting["catalog_id"] for meeting in response.json()["meetings"]] == [101]
    finally:
        lineage_session.close()
        engine.dispose()


def test_lineage_endpoint_returns_ordered_meetings_from_database():
    rows = [
        (
            SimpleNamespace(
                id=102,
                lineage_id="lin-101",
                lineage_confidence=0.7,
                lineage_updated_at=None,
                summary="Later meeting",
            ),
            SimpleNamespace(),
            SimpleNamespace(name="Meeting B", record_date=SimpleNamespace(isoformat=lambda: "2025-02-10")),
            SimpleNamespace(display_name="Berkeley", name="Berkeley"),
        ),
        (
            SimpleNamespace(
                id=101,
                lineage_id="lin-101",
                lineage_confidence=0.8,
                lineage_updated_at=None,
                summary="Earlier meeting",
            ),
            SimpleNamespace(),
            SimpleNamespace(name="Meeting A", record_date=SimpleNamespace(isoformat=lambda: "2025-01-10")),
            SimpleNamespace(display_name="Berkeley", name="Berkeley"),
        ),
    ]
    db = MagicMock()
    lineage_query = db.query.return_value.join.return_value.join.return_value.join.return_value
    lineage_query.filter.return_value.order_by.return_value.all.return_value = rows

    response = _lineage_client(db).get("/lineage/lin-101")

    assert response.status_code == 200
    lineage = response.json()
    assert lineage["count"] == 2
    assert [meeting["catalog_id"] for meeting in lineage["meetings"]] == [102, 101]
