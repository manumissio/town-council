from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, cast

from pipeline.profile_manifest_candidates import (
    entity_reset_candidates,
    extract_candidates,
    org_reset_candidates,
    segment_reset_candidates,
    summary_reset_candidates,
)
from pipeline.profile_manifest_contracts import (
    AppliedPreconditioningCounts,
    JsonPayload,
    PHASE_ENTITY,
    PHASE_EXTRACT,
    PHASE_ORG,
    PHASE_SEGMENT,
    PHASE_SUMMARY,
    OrmSession,
    SessionFactory,
)
from pipeline.profile_manifest_io import extract_source_digests, sha256_file, validate_manifest_package


def _models() -> Any:
    return import_module("pipeline.models")  # SQLAlchemy ORM models stay outside this strict typed boundary.


def preconditioning_report(package: JsonPayload) -> JsonPayload:
    catalog_ids = [int(cid) for cid in package.get("catalog_ids") or []]
    strata = _phase_catalog_ids(package)
    entity_targets = sorted(set(strata.get(PHASE_ENTITY, [])))
    return {
        "schema_version": int(package.get("schema_version") or 0),
        "manifest_name": package.get("manifest_name"),
        "catalog_count": len(catalog_ids),
        "phase_selected_counts": {key: len(value) for key, value in strata.items()},
        "reset_actions": {
            "extract_catalogs": len(strata.get(PHASE_EXTRACT, [])),
            "segment_catalogs": len(strata.get(PHASE_SEGMENT, [])),
            "summary_catalogs": len(strata.get(PHASE_SUMMARY, [])),
            "entity_catalogs": len(entity_targets),
            "org_events": len(package.get("org_event_resets") or []),
        },
        "expected_phase_coverage": dict(package.get("expected_phase_coverage") or {}),
    }


def apply_preconditioning(
    package: JsonPayload,
    *,
    dry_run: bool,
    session_factory: SessionFactory,
) -> JsonPayload:
    raw_catalog_ids = package.get("catalog_ids")
    catalog_ids = cast(list[int], raw_catalog_ids) if isinstance(raw_catalog_ids, list) else []
    validate_manifest_package(catalog_ids, package)
    report = preconditioning_report(package)
    applied = _empty_applied_counts()
    reset_plan = _build_reset_plan(package)
    with session_factory() as session:
        _validate_reset_targets(session, reset_plan)
        _validate_extract_sources(session, reset_plan.extract_ids, extract_source_digests(package))
        if dry_run:
            return {"dry_run": True, "report": report, "applied": applied}
        if reset_plan.segment_ids:
            applied["deleted_agenda_items"] = _delete_agenda_items(session, reset_plan.segment_ids)
        if reset_plan.extract_ids:
            applied["cleared_extract_catalogs"] = _clear_extract_catalogs(session, reset_plan.extract_ids)
        if reset_plan.segment_ids:
            applied["cleared_segment_catalogs"] = _clear_segment_catalogs(session, reset_plan.segment_ids)
        if reset_plan.summary_ids:
            applied["cleared_summary_catalogs"] = _clear_summary_catalogs(session, reset_plan.summary_ids)
        if reset_plan.entity_ids:
            applied["cleared_entity_catalogs"] = _clear_entity_catalogs(session, reset_plan.entity_ids)
        if reset_plan.org_event_ids:
            applied["cleared_org_events"] = _clear_org_events(session, reset_plan.org_event_ids)
        session.commit()

    return {"dry_run": False, "report": report, "applied": applied}


class _ResetPlan:
    __slots__ = ("entity_ids", "extract_ids", "org_resets", "segment_ids", "summary_ids")

    def __init__(
        self,
        *,
        extract_ids: list[int],
        segment_ids: list[int],
        summary_ids: list[int],
        entity_ids: list[int],
        org_resets: list[tuple[int, int]],
    ) -> None:
        self.extract_ids = extract_ids
        self.segment_ids = segment_ids
        self.summary_ids = summary_ids
        self.entity_ids = entity_ids
        self.org_resets = org_resets

    @property
    def org_event_ids(self) -> list[int]:
        return [event_id for _catalog_id, event_id in self.org_resets]


def _build_reset_plan(package: JsonPayload) -> _ResetPlan:
    strata = _phase_catalog_ids(package)
    return _ResetPlan(
        extract_ids=strata.get(PHASE_EXTRACT, []),
        segment_ids=strata.get(PHASE_SEGMENT, []),
        summary_ids=strata.get(PHASE_SUMMARY, []),
        entity_ids=sorted(set(strata.get(PHASE_ENTITY, []))),
        org_resets=[
            (int(reset["catalog_id"]), int(reset["event_id"]))
            for reset in package.get("org_event_resets") or []
        ],
    )


def _phase_catalog_ids(package: JsonPayload) -> dict[str, list[int]]:
    return {key: [int(cid) for cid in value] for key, value in (package.get("strata") or {}).items()}


def _empty_applied_counts() -> AppliedPreconditioningCounts:
    return {
        "deleted_agenda_items": 0,
        "cleared_extract_catalogs": 0,
        "cleared_segment_catalogs": 0,
        "cleared_summary_catalogs": 0,
        "cleared_entity_catalogs": 0,
        "cleared_org_events": 0,
    }


def _validate_reset_targets(session: OrmSession, reset_plan: _ResetPlan) -> None:
    phase_targets = {
        PHASE_EXTRACT: reset_plan.extract_ids,
        PHASE_SEGMENT: reset_plan.segment_ids,
        PHASE_SUMMARY: reset_plan.summary_ids,
        PHASE_ENTITY: reset_plan.entity_ids,
    }
    phase_candidates = {
        PHASE_EXTRACT: extract_candidates(session),
        PHASE_SEGMENT: segment_reset_candidates(session),
        PHASE_SUMMARY: summary_reset_candidates(session),
        PHASE_ENTITY: entity_reset_candidates(session),
    }
    for phase, target_ids in phase_targets.items():
        eligible_ids = {int(candidate["catalog_id"]) for candidate in phase_candidates[phase]}
        invalid_ids = sorted(set(target_ids) - eligible_ids)
        if invalid_ids:
            raise ValueError(f"{phase} replay targets are no longer eligible: {invalid_ids}")

    eligible_org_resets = {
        (int(candidate["catalog_id"]), int(candidate["event_id"]))
        for candidate in org_reset_candidates(session)
    }
    invalid_org_resets = sorted(set(reset_plan.org_resets) - eligible_org_resets)
    if invalid_org_resets:
        raise ValueError(f"{PHASE_ORG} replay targets are no longer eligible: {invalid_org_resets}")


def _validate_extract_sources(
    session: OrmSession,
    extract_ids: list[int],
    expected_digests: dict[str, str],
) -> None:
    if not extract_ids:
        return

    models = _models()
    source_locations = {
        int(catalog_id): location
        for catalog_id, location in session.query(models.Catalog.id, models.Catalog.location)
        .filter(models.Catalog.id.in_(extract_ids))
        .all()
    }
    for catalog_id in extract_ids:
        location = source_locations.get(catalog_id)
        source_path = Path(str(location)) if location is not None else None
        if source_path is None or not source_path.is_file():
            raise ValueError(f"extract replay source is not a regular file for catalog_id={catalog_id}")
        if sha256_file(source_path) != expected_digests[str(catalog_id)]:
            raise ValueError(f"extract replay source digest mismatch for catalog_id={catalog_id}")


def _delete_agenda_items(session: OrmSession, catalog_ids: list[int]) -> int:
    models = _models()
    return int(
        session.query(models.AgendaItem)
        .filter(models.AgendaItem.catalog_id.in_(catalog_ids))
        .delete(synchronize_session=False)
        or 0
    )


def _clear_extract_catalogs(session: OrmSession, extract_ids: list[int]) -> int:
    models = _models()
    return int(
        session.query(models.Catalog)
        .filter(models.Catalog.id.in_(extract_ids))
        .update(
            {
                models.Catalog.content: None,
                models.Catalog.content_hash: None,
                models.Catalog.extraction_status: None,
                models.Catalog.extraction_attempted_at: None,
                models.Catalog.extraction_attempt_count: None,
                models.Catalog.extraction_error: None,
            },
            synchronize_session=False,
        )
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
                models.Catalog.summary: None,
                models.Catalog.summary_source_hash: None,
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
