from __future__ import annotations

from collections.abc import Iterator

import pytest
import requests

from pipeline.legistar_roster import fetch_legistar_roster
from pipeline.roster_contracts import (
    RosterBodyResolutionError,
    RosterPayloadError,
    RosterUnavailableError,
)


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _Session:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses: Iterator[_Response] = iter(responses)
        self.requested_urls: list[str] = []

    def get(self, url: str, *, timeout: tuple[float, float]) -> _Response:
        self.requested_urls.append(url)
        return next(self._responses)


class _TimeoutSession:
    def get(self, url: str, *, timeout: tuple[float, float]) -> _Response:
        raise requests.Timeout(f"timed out requesting {url}")


def _office_record(*, body_id: int = 777) -> dict[str, object]:
    return {
        "OfficeRecordId": 9001,
        "OfficeRecordGuid": "0f68f60b-21a1-43bc-a320-3e4bf376574c",
        "OfficeRecordLastModifiedUtc": "2026-07-31T14:05:06.123",
        "OfficeRecordFullName": "Roster Member",
        "OfficeRecordStartDate": "2025-01-01T00:00:00",
        "OfficeRecordEndDate": None,
        "OfficeRecordPersonId": 501,
        "OfficeRecordBodyId": body_id,
        "OfficeRecordTitle": "Councilmember",
        "OfficeRecordMemberType": "Member",
        "OfficeRecordEmail": "must-not-be-retained@example.com",
    }


def test_fetch_legistar_roster_resolves_body_before_office_records() -> None:
    http_session = _Session(
        [
            _Response(
                [
                    {
                        "BodyId": 777,
                        "BodyGuid": "d91d7235-85bd-4a3d-b0f3-2656d899dd11",
                        "BodyName": "City Council",
                        "BodyActiveFlag": 1,
                    }
                ]
            ),
            _Response([_office_record()]),
        ]
    )

    roster_snapshot = fetch_legistar_roster(
        "exampletenant",
        "City Council",
        http_session=http_session,
    )

    assert roster_snapshot.body.body_id == 777
    assert roster_snapshot.office_records[0].person_id == 501
    assert roster_snapshot.office_records[0].title == "Councilmember"
    assert not hasattr(roster_snapshot.office_records[0], "email")
    assert http_session.requested_urls == [
        "https://webapi.legistar.com/v1/exampletenant/Bodies",
        "https://webapi.legistar.com/v1/exampletenant/Bodies/777/OfficeRecords",
    ]


def test_fetch_legistar_roster_rejects_ambiguous_body_name() -> None:
    http_session = _Session(
        [
            _Response(
                [
                    {"BodyId": 100, "BodyGuid": "a", "BodyName": "City Council", "BodyActiveFlag": 1},
                    {"BodyId": 200, "BodyGuid": "b", "BodyName": " city  council ", "BodyActiveFlag": 1},
                ]
            )
        ]
    )

    with pytest.raises(RosterBodyResolutionError, match="exactly one active body"):
        fetch_legistar_roster("exampletenant", "City Council", http_session=http_session)


def test_fetch_legistar_roster_rejects_non_object_body() -> None:
    http_session = _Session([_Response([None])])

    with pytest.raises(RosterPayloadError, match="non-object body"):
        fetch_legistar_roster(
            "exampletenant",
            "City Council",
            http_session=http_session,
        )


def test_fetch_legistar_roster_rejects_record_for_another_body() -> None:
    http_session = _Session(
        [
            _Response([{"BodyId": 777, "BodyGuid": "a", "BodyName": "City Council", "BodyActiveFlag": 1}]),
            _Response([_office_record(body_id=888)]),
        ]
    )

    with pytest.raises(RosterPayloadError, match="body"):
        fetch_legistar_roster("exampletenant", "City Council", http_session=http_session)


def test_fetch_legistar_roster_accepts_authoritative_empty_snapshot() -> None:
    http_session = _Session(
        [
            _Response([{"BodyId": 777, "BodyGuid": "a", "BodyName": "City Council", "BodyActiveFlag": 1}]),
            _Response([]),
        ]
    )

    roster_snapshot = fetch_legistar_roster(
        "exampletenant",
        "City Council",
        http_session=http_session,
    )

    assert roster_snapshot.office_records == ()


def test_fetch_legistar_roster_wraps_transport_failure() -> None:
    with pytest.raises(RosterUnavailableError, match="exampletenant"):
        fetch_legistar_roster(
            "exampletenant",
            "City Council",
            http_session=_TimeoutSession(),
        )
