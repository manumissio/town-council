from __future__ import annotations

from typing import Final

import requests

from pipeline.inference_provider_contract import (
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


HTTP_CLIENT_ERROR_MIN_STATUS: Final = 400
HTTP_CLIENT_ERROR_MAX_STATUS: Final = 499


def response_error_for_client_http_error(error: requests.exceptions.HTTPError) -> ProviderResponseError | None:
    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if isinstance(status_code, int) and HTTP_CLIENT_ERROR_MIN_STATUS <= status_code <= HTTP_CLIENT_ERROR_MAX_STATUS:
        return ProviderResponseError(f"HTTP inference client error: status={status_code}")
    return None


def raise_provider_error_from_last_error(last_error: Exception | None) -> None:
    if isinstance(last_error, ProviderResponseError):
        raise last_error
    if isinstance(last_error, ProviderUnavailableError):
        raise last_error
    if isinstance(last_error, requests.exceptions.Timeout):
        raise ProviderTimeoutError(f"HTTP inference timed out: {last_error}") from last_error
    if last_error is not None:
        raise ProviderUnavailableError(f"HTTP inference unavailable: {last_error}") from last_error
    raise ProviderUnavailableError("HTTP inference unavailable")
