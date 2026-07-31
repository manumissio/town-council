#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from pipeline.legistar_roster import fetch_legistar_roster
from pipeline.models import Organization, Place, db_connect
from pipeline.rollout_registry import (
    CITY_METADATA_ALIASES,
    RolloutEntry,
    load_rollout_registry,
)
from pipeline.roster_contracts import (
    LegistarRosterSnapshot,
    RosterReconciliationCounts,
    RosterRunCounts,
    RosterSyncTarget,
)
from pipeline.roster_sync import depublish_city_roster, reconcile_roster_snapshot
from pipeline.utils import generate_ocd_id


def synchronize_rosters(
    *,
    city_slug: str | None,
    apply: bool,
) -> RosterRunCounts:
    selected_entries = _selected_entries(city_slug)
    engine = db_connect()
    session = sessionmaker(bind=engine)()
    run_counts = RosterRunCounts(
        cities_selected=len(selected_entries),
        applied=apply,
    )
    try:
        places_by_city = {
            rollout_entry.city_slug: _place_for_entry(session, rollout_entry)
            for rollout_entry in selected_entries
        }
        revoked_entries = [
            rollout_entry
            for rollout_entry in selected_entries
            if not rollout_entry.roster_authorized
        ]
        _depublish_revoked_entries(
            session,
            revoked_entries,
            places_by_city,
            run_counts,
        )
        if apply and revoked_entries:
            session.commit()
        roster_snapshots = _fetch_authorized_snapshots(
            selected_entries,
            places_by_city,
        )
        for rollout_entry in selected_entries:
            if not rollout_entry.roster_authorized:
                continue
            city_counts = _synchronize_entry(
                session,
                rollout_entry,
                places_by_city[rollout_entry.city_slug],
                roster_snapshots[rollout_entry.city_slug],
                datetime.now(tz=UTC),
            )
            _add_reconciliation_counts(run_counts, city_counts)
            run_counts.cities_synchronized += 1
        if apply:
            session.commit()
        else:
            session.rollback()
        return run_counts
    except (RuntimeError, SQLAlchemyError, ValueError):
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def _selected_entries(city_slug: str | None) -> list[RolloutEntry]:
    rollout_entries = load_rollout_registry()
    if city_slug is None:
        return rollout_entries
    selected_entries = [
        entry for entry in rollout_entries if entry.city_slug == city_slug
    ]
    if not selected_entries:
        raise ValueError(f"unknown city_slug in rollout registry: {city_slug}")
    return selected_entries


def _fetch_authorized_snapshots(
    rollout_entries: list[RolloutEntry],
    places_by_city: dict[str, Place],
) -> dict[str, LegistarRosterSnapshot]:
    snapshots: dict[str, LegistarRosterSnapshot] = {}
    for rollout_entry in rollout_entries:
        if not rollout_entry.roster_authorized:
            continue
        legistar_client = places_by_city[rollout_entry.city_slug].legistar_client
        if not legistar_client:
            raise ValueError(
                f"authorized city is missing legistar_client: "
                f"{rollout_entry.city_slug}"
            )
        snapshots[rollout_entry.city_slug] = fetch_legistar_roster(
            str(legistar_client),
            rollout_entry.roster_body_name,
        )
    return snapshots


def _depublish_revoked_entries(
    session: Session,
    revoked_entries: list[RolloutEntry],
    places_by_city: dict[str, Place],
    run_counts: RosterRunCounts,
) -> None:
    for rollout_entry in revoked_entries:
        city_counts = depublish_city_roster(
            session,
            int(places_by_city[rollout_entry.city_slug].id),
        )
        _add_reconciliation_counts(run_counts, city_counts)
        run_counts.cities_depublished += 1


def _synchronize_entry(
    session: Session,
    rollout_entry: RolloutEntry,
    place: Place,
    roster_snapshot: LegistarRosterSnapshot,
    synced_at: datetime,
) -> RosterReconciliationCounts:
    place_id = int(place.id)
    if not place.legistar_client:
        raise ValueError(
            f"authorized roster source is incomplete for {rollout_entry.city_slug}"
        )
    organization = _organization_for_snapshot(
        session,
        place,
        rollout_entry,
        roster_snapshot,
    )
    session.flush()
    city_counts = reconcile_roster_snapshot(
        session,
        RosterSyncTarget(
            place_id=place_id,
            organization_id=int(organization.id),
            city_slug=rollout_entry.city_slug,
            legistar_client=str(place.legistar_client),
            body_name=rollout_entry.roster_body_name,
        ),
        roster_snapshot,
        synced_at,
    )
    superseded_counts = depublish_city_roster(
        session,
        place_id,
        preserving_organization_id=int(organization.id),
    )
    city_counts.people_deleted += superseded_counts.people_deleted
    city_counts.memberships_deleted += superseded_counts.memberships_deleted
    return city_counts


def _place_for_entry(session: Session, rollout_entry: RolloutEntry) -> Place:
    metadata_slug = CITY_METADATA_ALIASES.get(
        rollout_entry.city_slug,
        rollout_entry.city_slug,
    )
    place = (
        session.query(Place)
        .filter(
            Place.ocd_division_id.endswith(
                f"/place:{metadata_slug}",
                autoescape=True,
            )
        )
        .one_or_none()
    )
    if place is None:
        raise ValueError(f"city is not seeded: {rollout_entry.city_slug}")
    return place


def _organization_for_snapshot(
    session: Session,
    place: Place,
    rollout_entry: RolloutEntry,
    roster_snapshot: LegistarRosterSnapshot,
) -> Organization:
    organization = (
        session.query(Organization)
        .filter(
            Organization.place_id == place.id,
            Organization.legistar_body_id == roster_snapshot.body.body_id,
        )
        .one_or_none()
    )
    if organization is not None:
        return organization
    named_organizations = (
        session.query(Organization)
        .filter(
            Organization.place_id == place.id,
            Organization.name == rollout_entry.roster_body_name,
        )
        .all()
    )
    if len(named_organizations) > 1:
        raise ValueError(
            f"multiple local organizations match {rollout_entry.city_slug}"
        )
    if named_organizations:
        return named_organizations[0]
    organization = Organization(
        ocd_id=generate_ocd_id("organization"),
        place_id=place.id,
        name=roster_snapshot.body.name,
        classification="legislature",
    )
    session.add(organization)
    return organization


def _add_reconciliation_counts(
    run_counts: RosterRunCounts,
    city_counts: RosterReconciliationCounts,
) -> None:
    run_counts.people_created += city_counts.people_created
    run_counts.people_updated += city_counts.people_updated
    run_counts.people_deleted += city_counts.people_deleted
    run_counts.memberships_created += city_counts.memberships_created
    run_counts.memberships_updated += city_counts.memberships_updated
    run_counts.memberships_deleted += city_counts.memberships_deleted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize only independently authorized city rosters."
    )
    parser.add_argument("--city", help="Limit synchronization to one registry slug.")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--dry-run", action="store_true")
    operation.add_argument("--apply", action="store_true")
    arguments = parser.parse_args(argv)
    run_counts = synchronize_rosters(
        city_slug=arguments.city,
        apply=arguments.apply,
    )
    print(json.dumps(asdict(run_counts), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
