#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import TypedDict

from sqlalchemy import JSON, Connection, bindparam, text

from pipeline.models import db_connect


class PersonRemediationCounts(TypedDict):
    catalogs_with_person_entities: int
    memberships: int
    people: int
    applied: bool


def remediate_legacy_people(
    connection: Connection,
    *,
    apply: bool,
) -> PersonRemediationCounts:
    catalog_rows = connection.execute(
        text("SELECT id, entities FROM catalog WHERE entities IS NOT NULL")
    ).all()
    catalogs_with_person_entities = [
        (int(catalog_id), entities)
        for catalog_id, entities in catalog_rows
        if _has_person_entities(entities)
    ]
    counts: PersonRemediationCounts = {
        "catalogs_with_person_entities": len(catalogs_with_person_entities),
        "memberships": int(
            connection.scalar(text("SELECT COUNT(*) FROM membership")) or 0
        ),
        "people": int(connection.scalar(text("SELECT COUNT(*) FROM person")) or 0),
        "applied": apply,
    }
    if not apply:
        return counts
    connection.execute(text("DELETE FROM membership"))
    connection.execute(text("DELETE FROM person"))
    for catalog_id, entities in catalogs_with_person_entities:
        cleaned_entities = _without_person_entities(entities)
        update_catalog = text(
            "UPDATE catalog SET entities = :entities WHERE id = :catalog_id"
        ).bindparams(bindparam("entities", type_=JSON))
        connection.execute(
            update_catalog,
            {
                "catalog_id": catalog_id,
                "entities": cleaned_entities,
            },
        )
    return counts


def _decoded_entities(entities: object) -> dict[str, object] | None:
    if isinstance(entities, dict):
        return dict(entities)
    if isinstance(entities, str):
        try:
            decoded = json.loads(entities)
        except json.JSONDecodeError as error:
            raise ValueError("catalog entities contains malformed JSON") from error
        if isinstance(decoded, dict):
            return decoded
    return None


def _has_person_entities(entities: object) -> bool:
    decoded_entities = _decoded_entities(entities)
    return decoded_entities is not None and "persons" in decoded_entities


def _without_person_entities(entities: object) -> dict[str, object]:
    decoded_entities = _decoded_entities(entities)
    if decoded_entities is None:
        raise ValueError("catalog entities must be a JSON object")
    decoded_entities.pop("persons", None)
    return decoded_entities


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove non-authoritative derived people before T-GOV-2A migration."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete legacy derived rows. The default is a read-only report.",
    )
    args = parser.parse_args(argv)
    engine = db_connect()
    with engine.begin() as connection:
        counts = remediate_legacy_people(connection, apply=args.apply)
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
