from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Membership, Organization, Person, Place
from pipeline.rollout_registry import RolloutEntry
from pipeline.roster_contracts import (
    LegistarRosterSnapshot,
    RosterBody,
    RosterOfficeRecord,
)
from scripts import sync_rosters


SYNCED_AT = datetime(2026, 7, 31, tzinfo=UTC)


def _snapshot() -> LegistarRosterSnapshot:
    return LegistarRosterSnapshot(
        body=RosterBody(body_id=777, body_guid="body-guid", name="City Council"),
        office_records=(
            RosterOfficeRecord(
                office_record_id=9001,
                office_record_guid="record-guid",
                person_id=501,
                full_name="Roster Member",
                title="Councilmember",
                member_type="Member",
                start_date=date(2025, 1, 1),
                end_date=None,
                last_modified_at=SYNCED_AT,
            ),
        ),
    )


def _authorized_entry(
    city_slug: str = "cupertino",
    roster_body_name: str = "City Council",
) -> RolloutEntry:
    return RolloutEntry(
        city_slug=city_slug,
        wave="wave1",
        enabled="yes",
        quality_gate="pass",
        stable_noop_eligible="no",
        last_verified_run_id="",
        last_verified_at="2026-07-31",
        last_fresh_pass_run_id="",
        roster_source="legistar_office_records",
        roster_body_name=roster_body_name,
        roster_source_verified_at="2026-07-31",
    )


def _database(monkeypatch, tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rosters.sqlite'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(
            Place(
                name="cupertino",
                state="CA",
                ocd_division_id="ocd-division/country:us/state:ca/place:cupertino",
                legistar_client="cupertino",
            )
        )
        session.commit()
    monkeypatch.setattr(sync_rosters, "db_connect", lambda: engine)
    monkeypatch.setattr(
        sync_rosters,
        "fetch_legistar_roster",
        lambda _client, _body: _snapshot(),
    )
    return engine


def test_roster_sync_dry_run_rolls_back_authoritative_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = _database(monkeypatch, tmp_path)

    counts = sync_rosters.synchronize_rosters(city_slug="cupertino", apply=False)

    assert counts.cities_synchronized == 1
    with sessionmaker(bind=engine)() as session:
        assert session.query(Person).count() == 0
        assert session.query(Membership).count() == 0
    engine.dispose()


def test_roster_sync_apply_persists_authoritative_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = _database(monkeypatch, tmp_path)

    counts = sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)

    assert counts.people_created == 1
    assert counts.memberships_created == 1
    with sessionmaker(bind=engine)() as session:
        assert session.query(Person).one().name == "Roster Member"
        assert session.query(Membership).one().legistar_office_record_id == 9001
    engine.dispose()


def test_roster_sync_requires_exact_city_division_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'adversarial.sqlite'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(
            Place(
                name="adversarial",
                state="CA",
                ocd_division_id="ocd-division/country:us/state:ca/place:sanXleandro",
                legistar_client="sanleandro",
            )
        )
        session.commit()
    monkeypatch.setattr(sync_rosters, "db_connect", lambda: engine)
    monkeypatch.setattr(
        sync_rosters,
        "load_rollout_registry",
        lambda: [_authorized_entry(city_slug="san_leandro")],
    )

    with pytest.raises(ValueError, match="city is not seeded: san_leandro"):
        sync_rosters.synchronize_rosters(city_slug="san_leandro", apply=True)

    engine.dispose()


def test_roster_sync_depublishes_superseded_governing_body(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = _database(monkeypatch, tmp_path)
    sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)
    replacement_snapshot = LegistarRosterSnapshot(
        body=RosterBody(
            body_id=888,
            body_guid="replacement-body-guid",
            name="Town Council",
        ),
        office_records=_snapshot().office_records,
    )
    monkeypatch.setattr(
        sync_rosters,
        "load_rollout_registry",
        lambda: [_authorized_entry(roster_body_name="Town Council")],
    )
    monkeypatch.setattr(
        sync_rosters,
        "fetch_legistar_roster",
        lambda _client, _body: replacement_snapshot,
    )

    counts = sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)

    assert counts.memberships_deleted == 0
    with sessionmaker(bind=engine)() as session:
        roster_organizations = (
            session.query(Organization)
            .filter(Organization.roster_source_url.is_not(None))
            .all()
        )
        assert [organization.name for organization in roster_organizations] == [
            "Town Council"
        ]
        old_organization = (
            session.query(Organization)
            .filter(Organization.name == "City Council")
            .one()
        )
        assert old_organization.roster_source_url is None
        assert session.query(Membership).one().organization.name == "Town Council"
    engine.dispose()


def test_roster_sync_transport_failure_preserves_existing_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = _database(monkeypatch, tmp_path)
    sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)

    def fail_fetch(_client: str, _body: str) -> LegistarRosterSnapshot:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(sync_rosters, "fetch_legistar_roster", fail_fetch)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)
    with sessionmaker(bind=engine)() as session:
        assert session.query(Person).count() == 1
        assert session.query(Membership).count() == 1
    engine.dispose()


def test_roster_sync_revocation_depublishes_stale_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = _database(monkeypatch, tmp_path)
    sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)
    revoked_entry = RolloutEntry(
        city_slug="cupertino",
        wave="",
        enabled="yes",
        quality_gate="pass",
        stable_noop_eligible="no",
        last_verified_run_id="",
        last_verified_at="2026-07-31",
        last_fresh_pass_run_id="",
        roster_source="",
        roster_body_name="",
        roster_source_verified_at="",
    )
    monkeypatch.setattr(
        sync_rosters,
        "load_rollout_registry",
        lambda: [revoked_entry],
    )

    counts = sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)

    assert counts.cities_depublished == 1
    assert counts.memberships_deleted == 1
    assert counts.people_deleted == 1
    with sessionmaker(bind=engine)() as session:
        assert session.query(Person).count() == 0
        assert session.query(Membership).count() == 0
        organization = session.query(Organization).one()
        assert organization.roster_source_url is None
    engine.dispose()


def test_roster_sync_revocation_survives_another_city_provider_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = _database(monkeypatch, tmp_path)
    sync_rosters.synchronize_rosters(city_slug="cupertino", apply=True)
    with sessionmaker(bind=engine)() as session:
        session.add(
            Place(
                name="hayward",
                state="CA",
                ocd_division_id="ocd-division/country:us/state:ca/place:hayward",
                legistar_client="hayward",
            )
        )
        session.commit()
    revoked_cupertino = RolloutEntry(
        city_slug="cupertino",
        wave="",
        enabled="yes",
        quality_gate="pass",
        stable_noop_eligible="no",
        last_verified_run_id="",
        last_verified_at="2026-07-31",
        last_fresh_pass_run_id="",
        roster_source="",
        roster_body_name="",
        roster_source_verified_at="",
    )
    authorized_hayward = RolloutEntry(
        city_slug="hayward",
        wave="wave1",
        enabled="yes",
        quality_gate="pass",
        stable_noop_eligible="no",
        last_verified_run_id="",
        last_verified_at="2026-07-31",
        last_fresh_pass_run_id="",
        roster_source="legistar_office_records",
        roster_body_name="City Council",
        roster_source_verified_at="2026-07-31",
    )
    monkeypatch.setattr(
        sync_rosters,
        "load_rollout_registry",
        lambda: [revoked_cupertino, authorized_hayward],
    )

    def fail_fetch(_client: str, _body: str) -> LegistarRosterSnapshot:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(sync_rosters, "fetch_legistar_roster", fail_fetch)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        sync_rosters.synchronize_rosters(city_slug=None, apply=True)

    with sessionmaker(bind=engine)() as session:
        assert session.query(Person).count() == 0
        assert session.query(Membership).count() == 0
        organization = session.query(Organization).one()
        assert organization.roster_source_url is None
    engine.dispose()
