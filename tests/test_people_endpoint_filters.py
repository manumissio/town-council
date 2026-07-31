from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys

sys.modules["llama_cpp"] = MagicMock()
from api.main import app, get_db  # noqa: E402
from pipeline.models import Base, Membership, Organization, Person, Place  # noqa: E402

ROSTER_SYNCED_AT = datetime(2026, 7, 31, tzinfo=UTC)
PERSON_SOURCE_URL = "https://webapi.legistar.com/v1/Test/Persons/501"
BODY_SOURCE_URL = "https://webapi.legistar.com/v1/Test/Bodies/777"
OFFICE_RECORDS_SOURCE_URL = (
    "https://webapi.legistar.com/v1/Test/Bodies/777/OfficeRecords"
)
AUTHORIZED_ROSTER_ENTRY = SimpleNamespace(
    city_slug="san_leandro",
    roster_body_name="City Council",
    roster_authorized=True,
)
NORMALIZED_ROSTER_ENTRY = SimpleNamespace(
    city_slug="san_leandro",
    roster_body_name="  city   council  ",
    roster_authorized=True,
)
REVOKED_ROSTER_ENTRY = SimpleNamespace(
    city_slug="test",
    roster_body_name="",
    roster_authorized=False,
)


def _build_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def _person(name: str, person_id: int) -> Person:
    return Person(
        name=name,
        ocd_id=f"ocd-person/{person_id}",
        legistar_client="Test",
        legistar_person_id=person_id,
        roster_source_url=PERSON_SOURCE_URL,
        roster_synced_at=ROSTER_SYNCED_AT,
    )


def _seed_roster_backed_person(session) -> tuple[Person, Person]:
    place = Place(
        name="san leandro",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_leandro",
        legistar_client="Test",
    )
    organization = Organization(
        place=place,
        name="City Council",
        legistar_body_id=777,
        legistar_body_guid="00000000-0000-0000-0000-000000000777",
        roster_source_url=BODY_SOURCE_URL,
        roster_synced_at=ROSTER_SYNCED_AT,
    )
    roster_person = _person("Roster Member", 501)
    orphan_person = _person("Orphan Person", 502)
    session.add_all([organization, roster_person, orphan_person])
    session.flush()
    session.add(
        Membership(
            person=roster_person,
            organization=organization,
            label="Council Member",
            start_date=date(2024, 1, 1),
            legistar_client="Test",
            legistar_office_record_id=9001,
            legistar_office_record_guid="00000000-0000-0000-0000-000000009001",
            roster_source_url=OFFICE_RECORDS_SOURCE_URL,
            roster_last_modified_at=ROSTER_SYNCED_AT,
            roster_synced_at=ROSTER_SYNCED_AT,
        )
    )
    session.commit()
    return roster_person, orphan_person


def _seed_adversarial_city_roster(session) -> None:
    place = Place(
        name="adversarial",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:sanXleandro",
        legistar_client="Test",
    )
    organization = Organization(
        place=place,
        name="City Council",
        legistar_body_id=778,
        legistar_body_guid="00000000-0000-0000-0000-000000000778",
        roster_source_url=BODY_SOURCE_URL,
        roster_synced_at=ROSTER_SYNCED_AT,
    )
    roster_person = _person("Wrong Municipality", 503)
    session.add_all([organization, roster_person])
    session.flush()
    session.add(
        Membership(
            person=roster_person,
            organization=organization,
            label="Council Member",
            start_date=date(2024, 1, 1),
            legistar_client="Test",
            legistar_office_record_id=9002,
            legistar_office_record_guid="00000000-0000-0000-0000-000000009002",
            roster_source_url=OFFICE_RECORDS_SOURCE_URL,
            roster_last_modified_at=ROSTER_SYNCED_AT,
            roster_synced_at=ROSTER_SYNCED_AT,
        )
    )
    session.commit()


def _override_database(Session):
    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    return override_get_db


def test_people_endpoint_returns_only_people_with_authoritative_roster_memberships():
    engine, Session = _build_db()
    with Session() as seed_session:
        _seed_roster_backed_person(seed_session)

    app.dependency_overrides[get_db] = _override_database(Session)
    client = TestClient(app)

    try:
        with patch("api.people_routes.load_rollout_registry", return_value=[AUTHORIZED_ROSTER_ENTRY]):
            response = client.get("/people")
        assert response.status_code == 200
        response_payload = response.json()
        assert response_payload["total"] == 1
        assert response_payload["results"][0]["name"] == "Roster Member"
        assert "include_mentions" not in response_payload
    finally:
        del app.dependency_overrides[get_db]
        engine.dispose()


def test_people_endpoint_requires_exact_city_division_identity() -> None:
    engine, Session = _build_db()
    with Session() as seed_session:
        roster_person, _ = _seed_roster_backed_person(seed_session)
        roster_person_id = roster_person.id
        _seed_adversarial_city_roster(seed_session)

    app.dependency_overrides[get_db] = _override_database(Session)
    client = TestClient(app)

    try:
        with patch("api.people_routes.load_rollout_registry", return_value=[AUTHORIZED_ROSTER_ENTRY]):
            response = client.get("/people")

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["results"] == [
            {"id": roster_person_id, "name": "Roster Member"}
        ]
    finally:
        del app.dependency_overrides[get_db]
        engine.dispose()


def test_people_endpoint_normalizes_approved_body_names() -> None:
    engine, Session = _build_db()
    with Session() as seed_session:
        roster_person, _ = _seed_roster_backed_person(seed_session)
        roster_person_id = roster_person.id

    app.dependency_overrides[get_db] = _override_database(Session)
    client = TestClient(app)

    try:
        with patch(
            "api.people_routes.load_rollout_registry",
            return_value=[NORMALIZED_ROSTER_ENTRY],
        ):
            people_response = client.get("/people")
            person_response = client.get(f"/person/{roster_person_id}")

        assert people_response.status_code == 200
        assert people_response.json()["total"] == 1
        assert person_response.status_code == 200
        assert person_response.json()["roles"][0]["body"] == "City Council"
    finally:
        del app.dependency_overrides[get_db]
        engine.dispose()


def test_people_endpoint_pagination_is_stable_when_names_match() -> None:
    engine, Session = _build_db()
    with Session() as seed_session:
        roster_person, _ = _seed_roster_backed_person(seed_session)
        second_person = _person("Roster Member", 504)
        organization = seed_session.query(Organization).one()
        seed_session.add(second_person)
        seed_session.flush()
        seed_session.add(
            Membership(
                person=second_person,
                organization=organization,
                label="Council Member",
                start_date=date(2024, 1, 1),
                legistar_client="Test",
                legistar_office_record_id=9003,
                legistar_office_record_guid="00000000-0000-0000-0000-000000009003",
                roster_source_url=OFFICE_RECORDS_SOURCE_URL,
                roster_last_modified_at=ROSTER_SYNCED_AT,
                roster_synced_at=ROSTER_SYNCED_AT,
            )
        )
        seed_session.commit()
        expected_ids = [roster_person.id, second_person.id]

    app.dependency_overrides[get_db] = _override_database(Session)
    client = TestClient(app)

    try:
        with patch("api.people_routes.load_rollout_registry", return_value=[AUTHORIZED_ROSTER_ENTRY]):
            first_page = client.get("/people?limit=1&offset=0")
            second_page = client.get("/people?limit=1&offset=1")

        assert first_page.json()["results"][0]["id"] == expected_ids[0]
        assert second_page.json()["results"][0]["id"] == expected_ids[1]
    finally:
        del app.dependency_overrides[get_db]
        engine.dispose()


def test_people_endpoint_does_not_publish_include_mentions_query_contract():
    people_parameters = app.openapi()["paths"]["/people"]["get"]["parameters"]

    assert "include_mentions" not in {parameter["name"] for parameter in people_parameters}


def test_person_detail_returns_roster_history_and_hides_unlinked_people():
    engine, Session = _build_db()
    with Session() as seed_session:
        roster_person, orphan_person = _seed_roster_backed_person(seed_session)
        roster_person_id = roster_person.id
        orphan_person_id = orphan_person.id

    app.dependency_overrides[get_db] = _override_database(Session)
    client = TestClient(app)

    try:
        with patch("api.people_routes.load_rollout_registry", return_value=[AUTHORIZED_ROSTER_ENTRY]):
            roster_response = client.get(f"/person/{roster_person_id}")
            orphan_response = client.get(f"/person/{orphan_person_id}")

        assert roster_response.status_code == 200
        assert roster_response.json() == {
            "name": "Roster Member",
            "roles": [
                {
                    "body": "City Council",
                    "city": "San Leandro",
                    "role": "Council Member",
                    "start_date": "2024-01-01",
                    "end_date": None,
                }
            ],
        }
        assert orphan_response.status_code == 404
    finally:
        del app.dependency_overrides[get_db]
        engine.dispose()


def test_people_endpoints_hide_stale_rows_after_registry_authorization_is_revoked():
    engine, Session = _build_db()
    with Session() as seed_session:
        roster_person, _ = _seed_roster_backed_person(seed_session)
        roster_person_id = roster_person.id

    app.dependency_overrides[get_db] = _override_database(Session)
    client = TestClient(app)

    try:
        with patch("api.people_routes.load_rollout_registry", return_value=[REVOKED_ROSTER_ENTRY]):
            people_response = client.get("/people")
            person_response = client.get(f"/person/{roster_person_id}")

        assert people_response.status_code == 200
        assert people_response.json()["total"] == 0
        assert people_response.json()["results"] == []
        assert person_response.status_code == 404
    finally:
        del app.dependency_overrides[get_db]
        engine.dispose()


def test_people_endpoints_fail_closed_when_roster_authorization_is_unavailable():
    client = TestClient(app)

    with patch(
        "api.people_routes.load_rollout_registry",
        side_effect=OSError("registry unavailable"),
    ):
        people_response = client.get("/people")
        person_response = client.get("/person/1")

    assert people_response.status_code == 503
    assert people_response.json()["detail"] == "Roster authorization unavailable"
    assert person_response.status_code == 503
    assert person_response.json()["detail"] == "Roster authorization unavailable"
