from __future__ import annotations

from datetime import UTC, date, datetime
import re
from typing import Final

import requests

from pipeline.agenda_legistar import build_legistar_session
from pipeline.roster_contracts import (
    LegistarRosterSnapshot,
    RosterBody,
    RosterBodyResolutionError,
    RosterOfficeRecord,
    RosterPayloadError,
    RosterUnavailableError,
)


LEGISTAR_API_ROOT: Final = "https://webapi.legistar.com/v1"
LEGISTAR_CONNECT_TIMEOUT_SECONDS: Final = 3.0
LEGISTAR_READ_TIMEOUT_SECONDS: Final = 10.0
LEGISTAR_CLIENT_PATTERN: Final = re.compile(r"^[a-z0-9]+$")


def fetch_legistar_roster(
    legistar_client: str,
    body_name: str,
    *,
    http_session: requests.Session | None = None,
) -> LegistarRosterSnapshot:
    normalized_client = _validated_client(legistar_client)
    session = http_session or build_legistar_session()
    bodies_url = f"{LEGISTAR_API_ROOT}/{normalized_client}/Bodies"
    bodies_payload = _get_json_list(session, bodies_url, normalized_client)
    body = _resolve_body(bodies_payload, body_name)
    office_records_url = (
        f"{LEGISTAR_API_ROOT}/{normalized_client}/Bodies/"
        f"{body.body_id}/OfficeRecords"
    )
    records_payload = _get_json_list(
        session,
        office_records_url,
        normalized_client,
    )
    office_records = _parse_office_records(records_payload, body.body_id)
    return LegistarRosterSnapshot(body=body, office_records=office_records)


def _validated_client(legistar_client: str) -> str:
    normalized_client = legistar_client.strip().casefold()
    if not LEGISTAR_CLIENT_PATTERN.fullmatch(normalized_client):
        raise RosterPayloadError("Legistar client must contain lowercase letters and digits")
    return normalized_client


def _get_json_list(
    session: requests.Session,
    url: str,
    legistar_client: str,
) -> list[object]:
    try:
        response = session.get(
            url,
            timeout=(
                LEGISTAR_CONNECT_TIMEOUT_SECONDS,
                LEGISTAR_READ_TIMEOUT_SECONDS,
            ),
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RosterUnavailableError(
            f"Legistar roster unavailable for client={legistar_client}"
        ) from error
    try:
        payload = response.json()
    except requests.JSONDecodeError as error:
        raise RosterPayloadError(
            f"Legistar roster returned malformed JSON for client={legistar_client}"
        ) from error
    if not isinstance(payload, list):
        raise RosterPayloadError(
            f"Legistar roster returned a non-list payload for client={legistar_client}"
        )
    return payload


def _resolve_body(
    bodies_payload: list[object],
    configured_body_name: str,
) -> RosterBody:
    normalized_name = _normalized_text(configured_body_name).casefold()
    matching_bodies: list[RosterBody] = []
    for body_payload in bodies_payload:
        if not isinstance(body_payload, dict):
            raise RosterPayloadError("Legistar Bodies contains a non-object body")
        body_name = _required_text(body_payload, "BodyName")
        if body_name.casefold() != normalized_name:
            continue
        if body_payload.get("BodyActiveFlag") not in (1, True):
            continue
        matching_bodies.append(
            RosterBody(
                body_id=_required_positive_int(body_payload, "BodyId"),
                body_guid=_required_text(body_payload, "BodyGuid"),
                name=body_name,
            )
        )
    if len(matching_bodies) != 1:
        raise RosterBodyResolutionError(
            "Legistar roster requires exactly one active body matching "
            f"{configured_body_name!r}; found={len(matching_bodies)}"
        )
    return matching_bodies[0]


def _parse_office_records(
    records_payload: list[object],
    body_id: int,
) -> tuple[RosterOfficeRecord, ...]:
    office_records: list[RosterOfficeRecord] = []
    seen_record_ids: set[int] = set()
    for record_payload in records_payload:
        if not isinstance(record_payload, dict):
            raise RosterPayloadError("Legistar OfficeRecords contains a non-object record")
        office_record = _parse_office_record(record_payload, body_id)
        if office_record.office_record_id in seen_record_ids:
            raise RosterPayloadError(
                "Legistar OfficeRecords contains a duplicate office record ID"
            )
        seen_record_ids.add(office_record.office_record_id)
        office_records.append(office_record)
    return tuple(office_records)


def _parse_office_record(
    record_payload: dict[object, object],
    body_id: int,
) -> RosterOfficeRecord:
    record_body_id = _required_positive_int(record_payload, "OfficeRecordBodyId")
    if record_body_id != body_id:
        raise RosterPayloadError(
            "Legistar OfficeRecord body does not match the resolved body"
        )
    return RosterOfficeRecord(
        office_record_id=_required_positive_int(record_payload, "OfficeRecordId"),
        office_record_guid=_required_text(record_payload, "OfficeRecordGuid"),
        person_id=_required_positive_int(record_payload, "OfficeRecordPersonId"),
        full_name=_required_text(record_payload, "OfficeRecordFullName"),
        title=_optional_text(record_payload, "OfficeRecordTitle"),
        member_type=_optional_text(record_payload, "OfficeRecordMemberType"),
        start_date=_required_date(record_payload, "OfficeRecordStartDate"),
        end_date=_optional_date(record_payload, "OfficeRecordEndDate"),
        last_modified_at=_required_utc_datetime(
            record_payload,
            "OfficeRecordLastModifiedUtc",
        ),
    )


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _required_text(payload: dict[object, object], field_name: str) -> str:
    value = _normalized_text(payload.get(field_name))
    if not value:
        raise RosterPayloadError(f"Legistar roster field is missing: {field_name}")
    return value


def _optional_text(
    payload: dict[object, object],
    field_name: str,
) -> str | None:
    value = _normalized_text(payload.get(field_name))
    return value or None


def _required_positive_int(
    payload: dict[object, object],
    field_name: str,
) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool):
        raise RosterPayloadError(f"Legistar roster field is invalid: {field_name}")
    if isinstance(value, int):
        parsed_value = value
    elif isinstance(value, str):
        try:
            parsed_value = int(value)
        except ValueError as error:
            raise RosterPayloadError(
                f"Legistar roster field is invalid: {field_name}"
            ) from error
    else:
        raise RosterPayloadError(f"Legistar roster field is invalid: {field_name}")
    if parsed_value <= 0:
        raise RosterPayloadError(f"Legistar roster field is invalid: {field_name}")
    return parsed_value


def _required_date(
    payload: dict[object, object],
    field_name: str,
) -> date:
    value = _required_text(payload, field_name)
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as error:
        raise RosterPayloadError(
            f"Legistar roster date is invalid: {field_name}"
        ) from error


def _optional_date(
    payload: dict[object, object],
    field_name: str,
) -> date | None:
    value = _optional_text(payload, field_name)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as error:
        raise RosterPayloadError(
            f"Legistar roster date is invalid: {field_name}"
        ) from error


def _required_utc_datetime(
    payload: dict[object, object],
    field_name: str,
) -> datetime:
    value = _required_text(payload, field_name)
    try:
        parsed_value = datetime.fromisoformat(value)
    except ValueError as error:
        raise RosterPayloadError(
            f"Legistar roster timestamp is invalid: {field_name}"
        ) from error
    if parsed_value.tzinfo is None:
        return parsed_value.replace(tzinfo=UTC)
    return parsed_value.astimezone(UTC)
