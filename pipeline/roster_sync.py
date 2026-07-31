from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_attribute

from pipeline.models import Membership, Organization, Person
from pipeline.roster_contracts import (
    LegistarRosterSnapshot,
    RosterReconciliationCounts,
    RosterOfficeRecord,
    RosterSyncTarget,
)
from pipeline.utils import generate_ocd_id


LEGISTAR_API_ROOT = "https://webapi.legistar.com/v1"


def reconcile_roster_snapshot(
    session: Session,
    sync_target: RosterSyncTarget,
    roster_snapshot: LegistarRosterSnapshot,
    synced_at: datetime,
) -> RosterReconciliationCounts:
    if synced_at.tzinfo is None:
        raise ValueError("roster sync timestamp must be timezone-aware")
    organization = session.get(Organization, sync_target.organization_id)
    if organization is None or organization.place_id != sync_target.place_id:
        raise ValueError("roster sync target does not match a local organization")
    counts = RosterReconciliationCounts()
    _update_organization(organization, sync_target, roster_snapshot, synced_at)
    current_record_ids: set[int] = set()
    for office_record in roster_snapshot.office_records:
        person, person_created, person_updated = _upsert_person(
            session,
            sync_target,
            office_record,
            synced_at,
        )
        counts.people_created += int(person_created)
        counts.people_updated += int(person_updated)
        membership_created, membership_updated = _upsert_membership(
            session,
            sync_target,
            roster_snapshot,
            office_record,
            person,
            synced_at,
        )
        counts.memberships_created += int(membership_created)
        counts.memberships_updated += int(membership_updated)
        current_record_ids.add(office_record.office_record_id)
    deleted_memberships, deleted_people = _delete_stale_records(
        session,
        sync_target,
        current_record_ids,
    )
    counts.memberships_deleted = deleted_memberships
    counts.people_deleted = deleted_people
    return counts


def _update_organization(
    organization: Organization,
    sync_target: RosterSyncTarget,
    roster_snapshot: LegistarRosterSnapshot,
    synced_at: datetime,
) -> None:
    set_attribute(organization, "name", roster_snapshot.body.name)
    set_attribute(organization, "legistar_body_id", roster_snapshot.body.body_id)
    set_attribute(organization, "legistar_body_guid", roster_snapshot.body.body_guid)
    source_url = (
        f"{LEGISTAR_API_ROOT}/{sync_target.legistar_client}/Bodies/"
        f"{roster_snapshot.body.body_id}"
    )
    set_attribute(organization, "roster_source_url", source_url)
    set_attribute(organization, "roster_synced_at", synced_at)


def _upsert_person(
    session: Session,
    sync_target: RosterSyncTarget,
    office_record: RosterOfficeRecord,
    synced_at: datetime,
) -> tuple[Person, bool, bool]:
    person_id = office_record.person_id
    full_name = office_record.full_name
    person = (
        session.query(Person)
        .filter(
            Person.legistar_client == sync_target.legistar_client,
            Person.legistar_person_id == person_id,
        )
        .one_or_none()
    )
    source_url = (
        f"{LEGISTAR_API_ROOT}/{sync_target.legistar_client}/Persons/{person_id}"
    )
    if person is None:
        person = Person(
            ocd_id=generate_ocd_id("person"),
            name=full_name,
            legistar_client=sync_target.legistar_client,
            legistar_person_id=person_id,
            roster_source_url=source_url,
            roster_synced_at=synced_at,
        )
        session.add(person)
        session.flush()
        return person, True, False
    changed = (
        _instance_value(person, "name") != full_name
        or _instance_value(person, "roster_source_url") != source_url
    )
    set_attribute(person, "name", full_name)
    set_attribute(person, "roster_source_url", source_url)
    set_attribute(person, "roster_synced_at", synced_at)
    return person, False, changed


def _upsert_membership(
    session: Session,
    sync_target: RosterSyncTarget,
    roster_snapshot: LegistarRosterSnapshot,
    office_record: RosterOfficeRecord,
    person: Person,
    synced_at: datetime,
) -> tuple[bool, bool]:
    office_record_id = office_record.office_record_id
    membership = (
        session.query(Membership)
        .filter(
            Membership.legistar_client == sync_target.legistar_client,
            Membership.legistar_office_record_id == office_record_id,
        )
        .one_or_none()
    )
    source_url = (
        f"{LEGISTAR_API_ROOT}/{sync_target.legistar_client}/Bodies/"
        f"{roster_snapshot.body.body_id}/OfficeRecords"
    )
    person_id = _instance_int(person, "id")
    label = office_record.title or office_record.member_type or "Member"
    role = office_record.member_type or "member"
    if membership is None:
        session.add(
            Membership(
                person_id=person_id,
                organization_id=sync_target.organization_id,
                label=label,
                role=role,
                start_date=office_record.start_date,
                end_date=office_record.end_date,
                legistar_client=sync_target.legistar_client,
                legistar_office_record_id=office_record_id,
                legistar_office_record_guid=office_record.office_record_guid,
                roster_source_url=source_url,
                roster_last_modified_at=office_record.last_modified_at,
                roster_synced_at=synced_at,
            )
        )
        return True, False
    changed = (
        _instance_value(membership, "person_id") != person_id
        or _instance_value(membership, "organization_id")
        != sync_target.organization_id
        or _instance_value(membership, "label") != label
        or _instance_value(membership, "role") != role
        or _instance_value(membership, "start_date") != office_record.start_date
        or _instance_value(membership, "end_date") != office_record.end_date
        or _instance_value(membership, "legistar_office_record_guid")
        != office_record.office_record_guid
        or _instance_value(membership, "roster_source_url") != source_url
        or not _same_timestamp(
            _instance_datetime(membership, "roster_last_modified_at"),
            office_record.last_modified_at,
        )
    )
    set_attribute(membership, "person_id", person_id)
    set_attribute(membership, "organization_id", sync_target.organization_id)
    set_attribute(membership, "label", label)
    set_attribute(membership, "role", role)
    set_attribute(membership, "start_date", office_record.start_date)
    set_attribute(membership, "end_date", office_record.end_date)
    set_attribute(
        membership,
        "legistar_office_record_guid",
        office_record.office_record_guid,
    )
    set_attribute(membership, "roster_source_url", source_url)
    set_attribute(
        membership,
        "roster_last_modified_at",
        office_record.last_modified_at,
    )
    set_attribute(membership, "roster_synced_at", synced_at)
    return False, changed


def _same_timestamp(stored_at: datetime, source_at: datetime) -> bool:
    normalized_stored_at = (
        stored_at.replace(tzinfo=UTC) if stored_at.tzinfo is None else stored_at.astimezone(UTC)
    )
    return normalized_stored_at == source_at.astimezone(UTC)


def _instance_value(model: object, attribute_name: str) -> object:
    return vars(model).get(attribute_name)


def _instance_datetime(model: object, attribute_name: str) -> datetime:
    stored_at = _instance_value(model, attribute_name)
    if not isinstance(stored_at, datetime):
        raise TypeError(f"{attribute_name} must be a datetime")
    return stored_at


def _delete_stale_records(
    session: Session,
    sync_target: RosterSyncTarget,
    current_record_ids: set[int],
) -> tuple[int, int]:
    stale_query = session.query(Membership).filter(
        Membership.organization_id == sync_target.organization_id,
        Membership.legistar_client == sync_target.legistar_client,
    )
    if current_record_ids:
        stale_query = stale_query.filter(
            Membership.legistar_office_record_id.notin_(current_record_ids)
        )
    stale_memberships = stale_query.all()
    return _delete_memberships_and_orphans(session, stale_memberships)


def _delete_memberships_and_orphans(
    session: Session,
    stale_memberships: list[Membership],
) -> tuple[int, int]:
    stale_person_ids = {
        _instance_int(membership, "person_id") for membership in stale_memberships
    }
    for membership in stale_memberships:
        session.delete(membership)
    session.flush()
    deleted_people = 0
    for person_id in stale_person_ids:
        remaining_membership = session.query(Membership.id).filter(
            Membership.person_id == person_id
        ).first()
        if remaining_membership is None:
            person = session.get(Person, person_id)
            if person is not None:
                session.delete(person)
                deleted_people += 1
    return len(stale_memberships), deleted_people


def _instance_int(model: object, attribute_name: str) -> int:
    stored_id = _instance_value(model, attribute_name)
    if not isinstance(stored_id, int):
        raise TypeError(f"{attribute_name} must be an integer")
    return stored_id


def depublish_city_roster(
    session: Session,
    place_id: int,
    preserving_organization_id: int | None = None,
) -> RosterReconciliationCounts:
    organizations_query = session.query(Organization).filter(
        Organization.place_id == place_id,
        Organization.roster_source_url.is_not(None),
    )
    if preserving_organization_id is not None:
        organizations_query = organizations_query.filter(
            Organization.id != preserving_organization_id
        )
    organizations = organizations_query.all()
    counts = RosterReconciliationCounts()
    for organization in organizations:
        organization_id = _instance_int(organization, "id")
        stale_memberships = (
            session.query(Membership)
            .filter(Membership.organization_id == organization_id)
            .all()
        )
        deleted_memberships, deleted_people = _delete_memberships_and_orphans(
            session,
            stale_memberships,
        )
        counts.memberships_deleted += deleted_memberships
        counts.people_deleted += deleted_people
        set_attribute(organization, "legistar_body_id", None)
        set_attribute(organization, "legistar_body_guid", None)
        set_attribute(organization, "roster_source_url", None)
        set_attribute(organization, "roster_synced_at", None)
    return counts
