from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Membership, Organization, Person, Place
from pipeline.roster_contracts import (
    LegistarRosterSnapshot,
    RosterBody,
    RosterOfficeRecord,
    RosterSyncTarget,
)
from pipeline.roster_sync import reconcile_roster_snapshot


SYNCED_AT = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)


def _snapshot(*, title: str = "Councilmember") -> LegistarRosterSnapshot:
    return LegistarRosterSnapshot(
        body=RosterBody(
            body_id=777,
            body_guid="d91d7235-85bd-4a3d-b0f3-2656d899dd11",
            name="City Council",
        ),
        office_records=(
            RosterOfficeRecord(
                office_record_id=9001,
                office_record_guid="0f68f60b-21a1-43bc-a320-3e4bf376574c",
                person_id=501,
                full_name="Roster Member",
                title=title,
                member_type="Member",
                start_date=date(2025, 1, 1),
                end_date=None,
                last_modified_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
            ),
        ),
    )


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def test_reconcile_roster_snapshot_is_idempotent_and_updates_public_role() -> None:
    engine, session = _session()
    place = Place(
        name="Example",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:example",
        legistar_client="exampletenant",
    )
    organization = Organization(name="City Council", place=place)
    session.add_all([place, organization])
    session.commit()
    sync_target = RosterSyncTarget(
        place_id=place.id,
        organization_id=organization.id,
        city_slug="example",
        legistar_client="exampletenant",
        body_name="City Council",
    )

    first_counts = reconcile_roster_snapshot(session, sync_target, _snapshot(), SYNCED_AT)
    session.commit()
    second_counts = reconcile_roster_snapshot(
        session,
        sync_target,
        _snapshot(title="Mayor"),
        SYNCED_AT,
    )
    session.commit()
    third_counts = reconcile_roster_snapshot(
        session,
        sync_target,
        _snapshot(title="Mayor"),
        SYNCED_AT,
    )
    session.commit()

    assert first_counts.people_created == 1
    assert first_counts.memberships_created == 1
    assert second_counts.people_created == 0
    assert second_counts.memberships_created == 0
    assert second_counts.memberships_updated == 1
    assert third_counts.people_updated == 0
    assert third_counts.memberships_updated == 0
    assert session.query(Person).count() == 1
    assert session.query(Membership).count() == 1
    membership = session.query(Membership).one()
    assert membership.label == "Mayor"
    assert membership.legistar_client == "exampletenant"
    assert membership.legistar_office_record_id == 9001
    assert membership.roster_synced_at.replace(tzinfo=UTC) == SYNCED_AT
    session.close()
    engine.dispose()


def test_reconcile_roster_snapshot_removes_stale_membership_and_orphan_person() -> None:
    engine, session = _session()
    place = Place(
        name="Example",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:example",
        legistar_client="exampletenant",
    )
    organization = Organization(name="City Council", place=place)
    session.add_all([place, organization])
    session.commit()
    sync_target = RosterSyncTarget(
        place_id=place.id,
        organization_id=organization.id,
        city_slug="example",
        legistar_client="exampletenant",
        body_name="City Council",
    )
    reconcile_roster_snapshot(session, sync_target, _snapshot(), SYNCED_AT)
    session.commit()

    empty_snapshot = LegistarRosterSnapshot(
        body=_snapshot().body,
        office_records=(),
    )
    counts = reconcile_roster_snapshot(session, sync_target, empty_snapshot, SYNCED_AT)
    session.commit()

    assert counts.memberships_deleted == 1
    assert counts.people_deleted == 1
    assert session.query(Membership).count() == 0
    assert session.query(Person).count() == 0
    session.close()
    engine.dispose()
