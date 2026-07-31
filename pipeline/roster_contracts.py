from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


class RosterError(RuntimeError):
    """Base error for authoritative roster operations."""


class RosterUnavailableError(RosterError):
    """The authoritative roster source could not be reached."""


class RosterPayloadError(RosterError):
    """The authoritative source returned an invalid or incomplete payload."""


class RosterBodyResolutionError(RosterError):
    """The configured governing body did not resolve unambiguously."""


@dataclass(frozen=True, slots=True)
class RosterBody:
    body_id: int
    body_guid: str
    name: str


@dataclass(frozen=True, slots=True)
class RosterOfficeRecord:
    office_record_id: int
    office_record_guid: str
    person_id: int
    full_name: str
    title: str | None
    member_type: str | None
    start_date: date
    end_date: date | None
    last_modified_at: datetime


@dataclass(frozen=True, slots=True)
class LegistarRosterSnapshot:
    body: RosterBody
    office_records: tuple[RosterOfficeRecord, ...]


@dataclass(frozen=True, slots=True)
class RosterSyncTarget:
    place_id: int
    organization_id: int
    city_slug: str
    legistar_client: str
    body_name: str


@dataclass(slots=True)
class RosterReconciliationCounts:
    people_created: int = 0
    people_updated: int = 0
    people_deleted: int = 0
    memberships_created: int = 0
    memberships_updated: int = 0
    memberships_deleted: int = 0


@dataclass(slots=True)
class RosterRunCounts:
    cities_selected: int = 0
    cities_synchronized: int = 0
    cities_depublished: int = 0
    people_created: int = 0
    people_updated: int = 0
    people_deleted: int = 0
    memberships_created: int = 0
    memberships_updated: int = 0
    memberships_deleted: int = 0
    applied: bool = False
