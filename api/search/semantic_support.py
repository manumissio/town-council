from typing import Any

import httpx
from fastapi import HTTPException

from api.app_setup import SEMANTIC_SERVICE_URL
from api.search.support_core import (
    SEMANTIC_HEALTHCHECK_TIMEOUT_SECONDS,
    SEMANTIC_SEARCH_TIMEOUT_SECONDS,
    SEMANTIC_SERVICE_ERROR_DETAIL,
)


def _semantic_service_healthcheck() -> dict[str, Any]:
    try:
        response = httpx.get(f"{SEMANTIC_SERVICE_URL}/health", timeout=SEMANTIC_HEALTHCHECK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Semantic service unavailable: {exc}") from exc


def _semantic_service_get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.get(f"{SEMANTIC_SERVICE_URL}{path}", params=params, timeout=SEMANTIC_SEARCH_TIMEOUT_SECONDS)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Semantic service unavailable: {exc}") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        except ValueError:
            detail = response.text or SEMANTIC_SERVICE_ERROR_DETAIL
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()
