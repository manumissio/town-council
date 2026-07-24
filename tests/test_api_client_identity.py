from collections.abc import Mapping

import pytest
from starlette.requests import Request

from api import app_setup


CONFIGURED_API_KEY = "configured-api-key-for-rate-limit-tests"
CLIENT_HOST = "10.0.0.12"


def _request(*, client_host: str, headers: Mapping[str, str]) -> Request:
    scope = {
        "type": "http",
        "client": (client_host, 44321),
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
    }
    return Request(scope)


@pytest.mark.parametrize(
    ("forwarded_ip", "expected_key"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:0db8:0000:0000:0000:ff00:0042:8329", "2001:db8::ff00:42:8329"),
    ],
)
def test_valid_api_key_and_single_forwarded_ip_use_canonical_ip(
    monkeypatch: pytest.MonkeyPatch,
    forwarded_ip: str,
    expected_key: str,
) -> None:
    monkeypatch.setenv("API_AUTH_KEY", CONFIGURED_API_KEY)
    request = _request(
        client_host=CLIENT_HOST,
        headers={"X-API-Key": CONFIGURED_API_KEY, "X-Forwarded-For": forwarded_ip},
    )

    assert app_setup.rate_limit_client_key(request) == expected_key


@pytest.mark.parametrize(
    ("api_key", "forwarded_for"),
    [
        (None, "203.0.113.7"),
        ("wrong-api-key", "203.0.113.7"),
        (CONFIGURED_API_KEY, "not-an-ip"),
        (CONFIGURED_API_KEY, " 203.0.113.7 "),
        (CONFIGURED_API_KEY, "203.0.113.7, 198.51.100.4"),
    ],
)
def test_untrusted_or_ambiguous_forwarding_falls_back_to_request_client(
    monkeypatch: pytest.MonkeyPatch,
    api_key: str | None,
    forwarded_for: str,
) -> None:
    monkeypatch.setenv("API_AUTH_KEY", CONFIGURED_API_KEY)
    headers = {"X-Forwarded-For": forwarded_for}
    if api_key is not None:
        headers["X-API-Key"] = api_key
    request = _request(client_host=CLIENT_HOST, headers=headers)

    assert app_setup.rate_limit_client_key(request) == CLIENT_HOST


def test_two_trusted_forwarded_ips_produce_distinct_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_AUTH_KEY", CONFIGURED_API_KEY)
    first_request = _request(
        client_host=CLIENT_HOST,
        headers={"X-API-Key": CONFIGURED_API_KEY, "X-Forwarded-For": "203.0.113.7"},
    )
    second_request = _request(
        client_host=CLIENT_HOST,
        headers={"X-API-Key": CONFIGURED_API_KEY, "X-Forwarded-For": "198.51.100.4"},
    )

    first_key = app_setup.rate_limit_client_key(first_request)
    second_key = app_setup.rate_limit_client_key(second_request)

    assert first_key == "203.0.113.7"
    assert second_key == "198.51.100.4"
    assert first_key != second_key
