from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from pipeline.indexer import reindex_catalogs
from pipeline.models import Catalog, Document, Event, Organization, Place, db_connect
from pipeline.profiling import (
    EligibilityBoundary,
    append_phase_eligibility,
    profile_observer,
    profiling_enabled,
    selected_catalog_ids,
)
from pipeline.utils import generate_ocd_id


BASE_ORGANIZATION_NAME = "City Council"
ORGANIZATION_BACKFILL_PHASE = "org_backfill"
PARKS_ORGANIZATION_NAME = "Parks & Recreation Commission"
PLANNING_ORGANIZATION_NAME = "Planning Commission"

OrganizationTargetKey: TypeAlias = tuple[int, str]
OrganizationTargetMap: TypeAlias = dict[OrganizationTargetKey, Organization | None]


class OrganizationTargetAmbiguityError(RuntimeError):
    """Raised when profiling cannot identify one exact organization target."""


def _organization_name_for_event(event: Event) -> str:
    meeting_type = str(event.meeting_type or "").lower()
    if "planning commission" in meeting_type or "planning board" in meeting_type:
        return PLANNING_ORGANIZATION_NAME
    if "parks" in meeting_type:
        return PARKS_ORGANIZATION_NAME
    return BASE_ORGANIZATION_NAME


def _load_scoped_records(
    session: Session,
    scoped_catalog_ids: set[int] | None,
) -> tuple[list[Place], list[Event]]:
    event_query = session.query(Event)
    if scoped_catalog_ids is not None:
        event_query = (
            event_query.join(Document, Document.event_id == Event.id)
            .join(Catalog, Catalog.id == Document.catalog_id)
            .filter(Catalog.id.in_(sorted(scoped_catalog_ids)))
            .distinct()
        )
    events = event_query.order_by(Event.id.asc()).all()

    place_query = session.query(Place)
    if scoped_catalog_ids is not None:
        place_ids = sorted({int(event.place_id) for event in events})
        place_query = place_query.filter(Place.id.in_(place_ids))
    places = place_query.order_by(Place.id.asc()).all()
    return places, events


def _find_first_organization(
    session: Session,
    place_id: int,
    organization_name: str,
) -> Organization | None:
    return session.query(Organization).filter_by(place_id=place_id, name=organization_name).first()


def _find_exact_organization(
    session: Session,
    place_id: int,
    organization_name: str,
) -> Organization | None:
    organizations = (
        session.query(Organization)
        .filter_by(place_id=place_id, name=organization_name)
        .limit(2)
        .all()
    )
    if len(organizations) > 1:
        raise OrganizationTargetAmbiguityError(
            f"multiple organizations match place_id={place_id} name={organization_name!r}"
        )
    return organizations[0] if organizations else None


def _organization_obligations(
    session: Session,
    places: list[Place],
    events: list[Event],
) -> tuple[OrganizationTargetMap, list[int], list[int]]:
    target_keys = {(int(place.id), BASE_ORGANIZATION_NAME) for place in places}
    target_keys.update(
        (int(event.place_id), _organization_name_for_event(event))
        for event in events
    )
    targets = {
        target_key: _find_exact_organization(session, *target_key)
        for target_key in sorted(target_keys)
    }
    eligible_place_ids = [
        int(place.id)
        for place in places
        if targets[(int(place.id), BASE_ORGANIZATION_NAME)] is None
    ]
    eligible_event_ids = []
    for event in events:
        target = targets[(int(event.place_id), _organization_name_for_event(event))]
        if target is None or event.organization_id != target.id:
            eligible_event_ids.append(int(event.id))
    return targets, eligible_place_ids, eligible_event_ids


def _emit_organization_eligibility(
    boundary: EligibilityBoundary,
    eligible_place_ids: Iterable[int],
    eligible_event_ids: Iterable[int],
) -> None:
    append_phase_eligibility(
        phase=ORGANIZATION_BACKFILL_PHASE,
        boundary=boundary,
        subject="place",
        eligible_ids=list(eligible_place_ids),
    )
    append_phase_eligibility(
        phase=ORGANIZATION_BACKFILL_PHASE,
        boundary=boundary,
        subject="event",
        eligible_ids=list(eligible_event_ids),
    )


def _create_organization(
    session: Session,
    place_id: int,
    organization_name: str,
) -> Organization:
    organization = Organization(
        name=organization_name,
        classification=(
            "legislature"
            if organization_name == BASE_ORGANIZATION_NAME
            else "committee"
        ),
        place_id=place_id,
        ocd_id=generate_ocd_id("organization"),
    )
    session.add(organization)
    session.flush()
    return organization


def _resolve_organization(
    session: Session,
    target_key: OrganizationTargetKey,
    exact_targets: OrganizationTargetMap | None,
) -> Organization:
    organization = (
        exact_targets[target_key]
        if exact_targets is not None
        else _find_first_organization(session, *target_key)
    )
    if organization is None:
        organization = _create_organization(session, *target_key)
        if exact_targets is not None:
            exact_targets[target_key] = organization
    return organization


def _ensure_base_organizations(
    session: Session,
    places: list[Place],
    exact_targets: OrganizationTargetMap | None,
) -> None:
    for place in places:
        _resolve_organization(
            session,
            (int(place.id), BASE_ORGANIZATION_NAME),
            exact_targets,
        )


def _catalog_ids_for_event(session: Session, event_id: int) -> set[int]:
    return {
        int(catalog_id)
        for (catalog_id,) in (
            session.query(Catalog.id)
            .join(Document, Document.catalog_id == Catalog.id)
            .filter(Document.event_id == event_id)
            .distinct()
            .all()
        )
    }


def _link_events(
    session: Session,
    events: list[Event],
    exact_targets: OrganizationTargetMap | None,
) -> tuple[int, set[int]]:
    linked_count = 0
    changed_catalog_ids: set[int] = set()
    for event in events:
        target_key = (int(event.place_id), _organization_name_for_event(event))
        organization = _resolve_organization(session, target_key, exact_targets)
        if event.organization_id == organization.id:
            continue
        event.organization_id = organization.id
        linked_count += 1
        changed_catalog_ids.update(_catalog_ids_for_event(session, int(event.id)))
    return linked_count, changed_catalog_ids


def _reindex_changed_catalogs(changed_catalog_ids: set[int]) -> tuple[int, int]:
    if not changed_catalog_ids:
        return 0, 0
    reindex_summary = reindex_catalogs(changed_catalog_ids)
    print(
        "targeted_reindex_summary "
        f"considered={reindex_summary['catalogs_considered']} "
        f"reindexed={reindex_summary['catalogs_reindexed']} "
        f"failed={reindex_summary['catalogs_failed']}"
    )
    reindexed = reindex_summary["catalogs_reindexed"]
    failed_reindex = reindex_summary["catalogs_failed"]
    if not isinstance(reindexed, int) or not isinstance(failed_reindex, int):
        raise TypeError("reindex summary counts must be integers")
    return reindexed, failed_reindex


def run_organization_backfill_workload() -> dict[str, int]:
    print("Connecting to database for organization backfill...")
    scoped_catalog_ids = selected_catalog_ids()
    session = sessionmaker(bind=db_connect())()
    exact_targets: OrganizationTargetMap | None = None
    try:
        places, events = _load_scoped_records(session, scoped_catalog_ids)
        if profiling_enabled():
            exact_targets, eligible_place_ids, eligible_event_ids = _organization_obligations(
                session,
                places,
                events,
            )
            _emit_organization_eligibility("before", eligible_place_ids, eligible_event_ids)
        print(f"Ensuring base organizations for {len(places)} cities...")
        print(f"Found {len(events)} events to process.")
        _ensure_base_organizations(session, places, exact_targets)
        linked_count, changed_catalog_ids = _link_events(session, events, exact_targets)
        session.commit()
    except (OrganizationTargetAmbiguityError, SQLAlchemyError):
        session.rollback()
        raise
    finally:
        session.close()

    reindexed, failed_reindex = _reindex_changed_catalogs(changed_catalog_ids)
    print(f"Backfill complete. Linked {linked_count} events to organizations.")
    return {
        "selected": len(events),
        "linked": linked_count,
        "reindexed": reindexed,
        "failed_reindex": failed_reindex,
    }


def capture_organization_backfill_after_eligibility() -> None:
    if not profiling_enabled():
        return
    with profile_observer():
        session = sessionmaker(bind=db_connect())()
        try:
            places, events = _load_scoped_records(session, selected_catalog_ids())
            _targets, eligible_place_ids, eligible_event_ids = _organization_obligations(
                session,
                places,
                events,
            )
            _emit_organization_eligibility("after", eligible_place_ids, eligible_event_ids)
        finally:
            session.close()


def run_organization_backfill() -> dict[str, int]:
    counts = run_organization_backfill_workload()
    capture_organization_backfill_after_eligibility()
    return counts


def backfill_organizations() -> dict[str, int]:
    return run_organization_backfill()


if __name__ == "__main__":
    backfill_organizations()
