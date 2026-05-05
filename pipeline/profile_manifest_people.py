from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
import re
from typing import Any, Final, TypeAlias

from pipeline.profile_manifest_contracts import ManifestCandidate, OrmSession


def _models() -> Any:
    return import_module("pipeline.models")  # SQLAlchemy ORM models stay outside this strict typed boundary.


def _person_linker() -> Any:
    return import_module("pipeline.person_linker")  # Person-name heuristics remain existing policy owner.


def _utils() -> Any:
    return import_module("pipeline.utils")  # Existing human-name classifier remains policy owner.


OfficialTitleChecker: TypeAlias = Callable[[str], bool]
PersonNameNormalizer: TypeAlias = Callable[[str], str]
PersonNamePredicate: TypeAlias = Callable[[str], bool]

_PEOPLE_RESET_BLOCKED_TOKENS: Final = {
    "agency",
    "automated",
    "board",
    "camera",
    "cameras",
    "carbon",
    "city",
    "climate",
    "coalition",
    "committee",
    "commission",
    "community",
    "director",
    "council",
    "county",
    "district",
    "free",
    "license",
    "manager",
    "mayor",
    "monoxide",
    "plate",
    "program",
    "project",
    "readers",
    "chair",
    "skills",
    "supervisory",
    "vice",
}


def is_safe_people_reset_name(
    name: str,
    *,
    human_name_classifier: PersonNamePredicate | None = None,
) -> bool:
    is_human_name = human_name_classifier or _utils().is_likely_human_name
    if not name or not is_human_name(name):
        return False

    parts = name.split()
    if len(parts) < 2 or len(parts) > 4:
        return False

    # Preconditioning should only remove strong person mentions, not civic
    # groups or policy phrases that slipped into entity extraction.
    for part in parts:
        plain = re.sub(r"[^A-Za-z'.-]", "", part)
        if not plain:
            return False
        token = plain.strip(".").lower()
        if token in _PEOPLE_RESET_BLOCKED_TOKENS:
            return False
        if len(plain) == 1 and plain.isalpha():
            continue
        if len(plain) == 2 and plain.endswith(".") and plain[0].isalpha():
            continue
        if plain.isupper() and len(plain) > 2:
            continue
        if not plain[0].isupper():
            return False
    return True


def people_reset_candidates(
    session: OrmSession,
    *,
    models_module: Any | None = None,  # SQLAlchemy model module is dynamic at runtime.
    official_title_checker: OfficialTitleChecker | None = None,
    person_name_normalizer: PersonNameNormalizer | None = None,
    safe_name_predicate: PersonNamePredicate | None = None,
) -> list[ManifestCandidate]:
    models = models_module or _models()
    rows = (
        session.query(models.Catalog.id, models.Catalog.entities)
        .join(models.Document, models.Document.catalog_id == models.Catalog.id)
        .join(models.Event, models.Event.id == models.Document.event_id)
        .filter(models.Event.organization_id.is_not(None), models.Catalog.entities.is_not(None))
        .order_by(models.Catalog.id)
        .all()
    )
    safe_names_by_catalog, unique_names = _collect_safe_people_names(
        rows,
        official_title_checker=official_title_checker,
        person_name_normalizer=person_name_normalizer,
        safe_name_predicate=safe_name_predicate,
    )
    people_by_name, membership_person_ids = _load_existing_mentioned_people(session, unique_names, models)
    return _build_people_reset_candidates(safe_names_by_catalog, people_by_name, membership_person_ids)


def _collect_safe_people_names(
    rows: list[tuple[int, object]],
    *,
    official_title_checker: OfficialTitleChecker | None,
    person_name_normalizer: PersonNameNormalizer | None,
    safe_name_predicate: PersonNamePredicate | None,
) -> tuple[dict[int, list[str]], set[str]]:
    safe_names_by_catalog: dict[int, list[str]] = {}
    unique_names: set[str] = set()
    for catalog_id, entities in rows:
        reset_names = _safe_entity_person_names(
            entities,
            official_title_checker=official_title_checker,
            person_name_normalizer=person_name_normalizer,
            safe_name_predicate=safe_name_predicate,
        )
        if reset_names:
            deduped_names = sorted(set(reset_names))
            safe_names_by_catalog[int(catalog_id)] = deduped_names
            unique_names.update(deduped_names)
    return safe_names_by_catalog, unique_names


def _safe_entity_person_names(
    entities: object,
    *,
    official_title_checker: OfficialTitleChecker | None,
    person_name_normalizer: PersonNameNormalizer | None,
    safe_name_predicate: PersonNamePredicate | None,
) -> list[str]:
    if not isinstance(entities, dict):
        return []
    raw_persons = entities.get("persons") or []
    if not isinstance(raw_persons, list):
        return []
    reset_names: list[str] = []
    person_linker = _person_linker()
    has_title_context = official_title_checker or person_linker.has_official_title_context
    normalize_name = person_name_normalizer or person_linker.normalize_person_name
    is_safe_name = safe_name_predicate or is_safe_people_reset_name
    for raw_name in raw_persons:
        if not isinstance(raw_name, str) or has_title_context(raw_name):
            continue
        name = normalize_name(raw_name)
        if is_safe_name(name):
            reset_names.append(name)
    return reset_names


def _load_existing_mentioned_people(
    session: OrmSession,
    unique_names: set[str],
    models: Any,  # SQLAlchemy model module is dynamic at runtime.
) -> tuple[dict[str, list[Any]], set[int]]:
    if not unique_names:
        return {}, set()

    people_rows = session.query(models.Person).filter(models.Person.name.in_(sorted(unique_names))).all()
    people_by_name: dict[str, list[Any]] = {}
    mentioned_person_ids: list[int] = []
    for person in people_rows:
        people_by_name.setdefault(str(person.name), []).append(person)
        if person.person_type == "mentioned":
            mentioned_person_ids.append(int(person.id))

    if not mentioned_person_ids:
        return people_by_name, set()

    membership_rows = (
        session.query(models.Membership.person_id)
        .filter(models.Membership.person_id.in_(mentioned_person_ids))
        .distinct()
        .all()
    )
    return people_by_name, {int(row[0]) for row in membership_rows if row[0] is not None}


def _build_people_reset_candidates(
    safe_names_by_catalog: dict[int, list[str]],
    people_by_name: dict[str, list[Any]],
    membership_person_ids: set[int],
) -> list[ManifestCandidate]:
    candidates: list[ManifestCandidate] = []
    for catalog_id, candidate_names in safe_names_by_catalog.items():
        reset_names = _resettable_names_for_catalog(
            candidate_names,
            people_by_name,
            membership_person_ids,
        )
        if reset_names:
            candidates.append({"catalog_id": int(catalog_id), "reset_names": reset_names})
    return candidates


def _resettable_names_for_catalog(
    candidate_names: list[str],
    people_by_name: dict[str, list[Any]],
    membership_person_ids: set[int],
) -> list[str]:
    reset_names: list[str] = []
    for name in candidate_names:
        people = people_by_name.get(name) or []
        if not people:
            reset_names.append(name)
            continue
        if any(person.person_type == "mentioned" and int(person.id) not in membership_person_ids for person in people):
            reset_names.append(name)
    return reset_names
