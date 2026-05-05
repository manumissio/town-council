from __future__ import annotations

from importlib import import_module
from typing import Any

from pipeline.profile_manifest_contracts import (
    AppliedPreconditioningCounts,
    JsonPayload,
    PHASE_ENTITY,
    PHASE_PEOPLE,
    PHASE_SEGMENT,
    PHASE_SUMMARY,
    OrmSession,
    SessionFactory,
)


def _models() -> Any:
    return import_module("pipeline.models")  # SQLAlchemy ORM models stay outside this strict typed boundary.


def preconditioning_report(package: JsonPayload) -> JsonPayload:
    catalog_ids = [int(cid) for cid in package.get("catalog_ids") or []]
    strata = _phase_catalog_ids(package)
    entity_targets = sorted(set(strata.get(PHASE_ENTITY, []) + strata.get(PHASE_PEOPLE, [])))
    return {
        "schema_version": int(package.get("schema_version") or 0),
        "manifest_name": package.get("manifest_name"),
        "catalog_count": len(catalog_ids),
        "phase_selected_counts": {key: len(value) for key, value in strata.items()},
        "reset_actions": {
            "segment_catalogs": len(strata.get(PHASE_SEGMENT, [])),
            "summary_catalogs": len(strata.get(PHASE_SUMMARY, [])),
            "entity_catalogs": len(entity_targets),
            "org_events": len(package.get("org_event_resets") or []),
            "people_name_groups": len(package.get("people_reset_names") or []),
        },
        "expected_phase_coverage": dict(package.get("expected_phase_coverage") or {}),
    }


def apply_preconditioning(
    package: JsonPayload,
    *,
    dry_run: bool,
    session_factory: SessionFactory,
) -> JsonPayload:
    report = preconditioning_report(package)
    applied = _empty_applied_counts()
    if dry_run:
        return {"dry_run": True, "report": report, "applied": applied}

    reset_plan = _build_reset_plan(package)
    with session_factory() as session:
        if reset_plan.segment_ids:
            applied["deleted_agenda_items"] = _delete_agenda_items(session, reset_plan.segment_ids)
            applied["cleared_segment_catalogs"] = _clear_segment_catalogs(session, reset_plan.segment_ids)
        if reset_plan.summary_ids:
            applied["cleared_summary_catalogs"] = _clear_summary_catalogs(session, reset_plan.summary_ids)
        if reset_plan.entity_ids:
            applied["cleared_entity_catalogs"] = _clear_entity_catalogs(session, reset_plan.entity_ids)
        if reset_plan.org_event_ids:
            applied["cleared_org_events"] = _clear_org_events(session, reset_plan.org_event_ids)
        applied["deleted_people"] = _delete_reset_people(session, reset_plan.people_reset_names)
        session.commit()

    return {"dry_run": False, "report": report, "applied": applied}


class _ResetPlan:
    __slots__ = ("entity_ids", "org_event_ids", "people_reset_names", "segment_ids", "summary_ids")

    def __init__(
        self,
        *,
        segment_ids: list[int],
        summary_ids: list[int],
        entity_ids: list[int],
        org_event_ids: list[int],
        people_reset_names: dict[int, list[str]],
    ) -> None:
        self.segment_ids = segment_ids
        self.summary_ids = summary_ids
        self.entity_ids = entity_ids
        self.org_event_ids = org_event_ids
        self.people_reset_names = people_reset_names


def _build_reset_plan(package: JsonPayload) -> _ResetPlan:
    strata = _phase_catalog_ids(package)
    return _ResetPlan(
        segment_ids=strata.get(PHASE_SEGMENT, []),
        summary_ids=strata.get(PHASE_SUMMARY, []),
        entity_ids=sorted(set(strata.get(PHASE_ENTITY, []) + strata.get(PHASE_PEOPLE, []))),
        org_event_ids=[int(item["event_id"]) for item in package.get("org_event_resets") or []],
        people_reset_names={
            int(item["catalog_id"]): [str(name) for name in item.get("names") or []]
            for item in package.get("people_reset_names") or []
        },
    )


def _phase_catalog_ids(package: JsonPayload) -> dict[str, list[int]]:
    return {key: [int(cid) for cid in value] for key, value in (package.get("strata") or {}).items()}


def _empty_applied_counts() -> AppliedPreconditioningCounts:
    return {
        "deleted_agenda_items": 0,
        "cleared_segment_catalogs": 0,
        "cleared_summary_catalogs": 0,
        "cleared_entity_catalogs": 0,
        "cleared_org_events": 0,
        "deleted_people": 0,
    }


def _delete_agenda_items(session: OrmSession, segment_ids: list[int]) -> int:
    models = _models()
    return int(
        session.query(models.AgendaItem)
        .filter(models.AgendaItem.catalog_id.in_(segment_ids))
        .delete(synchronize_session=False)
        or 0
    )


def _clear_segment_catalogs(session: OrmSession, segment_ids: list[int]) -> int:
    models = _models()
    return int(
        session.query(models.Catalog)
        .filter(models.Catalog.id.in_(segment_ids))
        .update(
            {
                models.Catalog.agenda_segmentation_status: None,
                models.Catalog.agenda_segmentation_attempted_at: None,
                models.Catalog.agenda_segmentation_item_count: None,
                models.Catalog.agenda_segmentation_error: None,
                models.Catalog.agenda_items_hash: None,
                models.Catalog.summary: None,
                models.Catalog.summary_source_hash: None,
                models.Catalog.summary_extractive: None,
            },
            synchronize_session=False,
        )
        or 0
    )


def _clear_summary_catalogs(session: OrmSession, summary_ids: list[int]) -> int:
    models = _models()
    return int(
        session.query(models.Catalog)
        .filter(models.Catalog.id.in_(summary_ids))
        .update(
            {
                models.Catalog.agenda_items_hash: None,
                models.Catalog.summary: None,
                models.Catalog.summary_source_hash: None,
                models.Catalog.summary_extractive: None,
            },
            synchronize_session=False,
        )
        or 0
    )


def _clear_entity_catalogs(session: OrmSession, entity_ids: list[int]) -> int:
    models = _models()
    return int(
        session.query(models.Catalog)
        .filter(models.Catalog.id.in_(entity_ids))
        .update(
            {
                models.Catalog.entities: None,
                models.Catalog.entities_source_hash: None,
                models.Catalog.related_ids: None,
            },
            synchronize_session=False,
        )
        or 0
    )


def _clear_org_events(session: OrmSession, org_event_ids: list[int]) -> int:
    models = _models()
    return int(
        session.query(models.Event)
        .filter(models.Event.id.in_(org_event_ids))
        .update({models.Event.organization_id: None}, synchronize_session=False)
        or 0
    )


def _delete_reset_people(session: OrmSession, people_reset_names: dict[int, list[str]]) -> int:
    deleted_people = 0
    for names in people_reset_names.values():
        for name in names:
            deleted_people += _delete_reset_people_by_name(session, name)
    return deleted_people


def _delete_reset_people_by_name(session: OrmSession, name: str) -> int:
    models = _models()
    deleted_people = 0
    matching_people = session.query(models.Person).filter(models.Person.name == name).all()
    for person in matching_people:
        has_membership = (
            session.query(models.Membership.id).filter(models.Membership.person_id == person.id).first() is not None
        )
        if person.person_type == "mentioned" and not has_membership:
            session.delete(person)
            deleted_people += 1
    return deleted_people
