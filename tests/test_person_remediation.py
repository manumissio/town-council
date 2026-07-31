from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

from scripts.remediate_legacy_people import remediate_legacy_people


def _legacy_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE person (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
        connection.execute(
            text(
                "CREATE TABLE membership ("
                "id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL, organization_id INTEGER NOT NULL)"
            )
        )
        connection.execute(text("CREATE TABLE catalog (id INTEGER PRIMARY KEY, entities JSON)"))
        connection.execute(text("INSERT INTO person (id, name) VALUES (1, 'Derived Name')"))
        connection.execute(
            text("INSERT INTO membership (id, person_id, organization_id) VALUES (1, 1, 9)")
        )
        connection.execute(
            text("INSERT INTO catalog (id, entities) VALUES (1, :entities)"),
            {"entities": json.dumps({"persons": ["Derived Name"], "orgs": ["Council"], "locs": []})},
        )
    return engine


def test_person_remediation_defaults_to_observation() -> None:
    engine = _legacy_engine()

    with engine.begin() as connection:
        counts = remediate_legacy_people(connection, apply=False)

    assert counts == {
        "catalogs_with_person_entities": 1,
        "memberships": 1,
        "people": 1,
        "applied": False,
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM person")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM membership")) == 1
    engine.dispose()


def test_person_remediation_apply_deletes_derived_rows_but_preserves_other_entities() -> None:
    engine = _legacy_engine()

    with engine.begin() as connection:
        counts = remediate_legacy_people(connection, apply=True)

    assert counts["applied"] is True
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM person")) == 0
        assert connection.scalar(text("SELECT COUNT(*) FROM membership")) == 0
        stored_entities = connection.scalar(
            text("SELECT entities FROM catalog WHERE id = 1")
        )
    entities = (
        json.loads(stored_entities)
        if isinstance(stored_entities, str)
        else stored_entities
    )
    assert entities == {"orgs": ["Council"], "locs": []}
    engine.dispose()


def test_person_remediation_rejects_malformed_entity_json_before_deleting() -> None:
    engine = _legacy_engine()
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE catalog SET entities = '{not-json' WHERE id = 1")
        )

    with engine.begin() as connection, pytest.raises(
        ValueError,
        match="malformed JSON",
    ):
        remediate_legacy_people(connection, apply=True)

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM person")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM membership")) == 1
    engine.dispose()
