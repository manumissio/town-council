from __future__ import annotations

from collections.abc import Callable

import requests

from pipeline.inference_provider_contract import RESPONSE_FIELD_NAME, ProviderResponseError
from pipeline.provider_telemetry import TokenMetrics, parse_token_metrics


def build_request_payload(
    prompt: str,
    *,
    model_name: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, object]:
    return {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": int(max_tokens),
            "temperature": float(temperature),
        },
    }


def parse_response_payload(
    response: requests.Response,
    *,
    token_metrics_parser: Callable[[dict[str, object]], TokenMetrics] = parse_token_metrics,
) -> tuple[str, TokenMetrics]:
    try:
        payload = response.json()
    except ValueError as error:
        raise ProviderResponseError(f"Invalid JSON response payload: {error}") from error
    if not isinstance(payload, dict):
        raise ProviderResponseError("Invalid response payload type")

    token_metrics = token_metrics_parser(payload)
    raw_response = payload.get(RESPONSE_FIELD_NAME)
    if raw_response is None:
        raise ProviderResponseError("Missing response field in payload")
    if not isinstance(raw_response, str):
        raise ProviderResponseError("Invalid response field type in payload")
    text = raw_response.strip()
    if not text:
        raise ProviderResponseError("Empty response payload")
    return text, token_metrics
