from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from pipeline.models import Base, Membership, Organization, Person, Place
from pipeline.roster_contracts import (
    LegistarRosterSnapshot,
    RosterBody,
    RosterOfficeRecord,
    RosterSyncTarget,
)
from pipeline.roster_sync import reconcile_roster_snapshot


SYNCED_AT = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)


def _snapshot(
    *,
    title: str = "Councilmember",
    person_id: int = 501,
    full_name: str = "Roster Member",
) -> LegistarRosterSnapshot:
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
                person_id=person_id,
                full_name=full_name,
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


def _seed_reconciled_roster() -> tuple[Engine, Session, RosterSyncTarget]:
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
    return engine, session, sync_target


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


def test_reconcile_roster_snapshot_removes_person_displaced_from_office_record() -> None:
    engine, session, sync_target = _seed_reconciled_roster()

    counts = reconcile_roster_snapshot(
        session,
        sync_target,
        _snapshot(person_id=502, full_name="Corrected Roster Member"),
        SYNCED_AT,
    )
    session.commit()

    assert counts.people_created == 1
    assert counts.people_deleted == 1
    corrected_person = session.query(Person).one()
    assert corrected_person.name == "Corrected Roster Member"
    assert session.query(Membership).one().person_id == corrected_person.id
    session.close()
    engine.dispose()


def test_reconcile_roster_snapshot_preserves_displaced_person_with_membership() -> None:
    engine, session, sync_target = _seed_reconciled_roster()
    roster_person = session.query(Person).one()
    place = session.get(Place, sync_target.place_id)
    assert place is not None

    advisory_board = Organization(name="Advisory Board", place=place)
    session.add(advisory_board)
    session.flush()
    session.add(
        Membership(
            person_id=roster_person.id,
            organization_id=advisory_board.id,
            label="Member",
            role="Member",
            start_date=date(2025, 1, 1),
            end_date=None,
            legistar_client="exampletenant",
            legistar_office_record_id=9002,
            legistar_office_record_guid="f6f5daab-6284-48c2-b5bf-e3a0973b282a",
            roster_source_url="https://example.test/office-records",
            roster_last_modified_at=SYNCED_AT,
            roster_synced_at=SYNCED_AT,
        )
    )
    session.commit()

    preserved_counts = reconcile_roster_snapshot(
        session,
        sync_target,
        _snapshot(person_id=502, full_name="Corrected Roster Member"),
        SYNCED_AT,
    )
    session.commit()

    assert preserved_counts.people_deleted == 0
    assert sorted(person.name for person in session.query(Person).all()) == [
        "Corrected Roster Member",
        "Roster Member",
    ]
    session.close()
    engine.dispose()
