from __future__ import annotations

from collections.abc import Callable

import requests

from pipeline.inference_provider_contract import RESPONSE_FIELD_NAME, ProviderResponseError
from pipeline.provider_telemetry import TokenMetrics, parse_openai_token_metrics, parse_token_metrics


OPENAI_CHOICES_FIELD = "choices"
OPENAI_MESSAGE_FIELD = "message"
OPENAI_CONTENT_FIELD = "content"
OPENAI_ROLE_USER = "user"


def build_request_payload(
    prompt: str,
    *,
    model_name: str,
    max_tokens: int,
    temperature: float,
    context_window: int | None = None,
) -> dict[str, object]:
    options: dict[str, object] = {
        "num_predict": int(max_tokens),
        "temperature": float(temperature),
    }
    if context_window is not None and context_window > 0:
        options["num_ctx"] = int(context_window)
    return {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }


def build_openai_compatible_request_payload(
    prompt: str,
    *,
    model_name: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, object]:
    return {
        "model": model_name,
        "messages": [{"role": OPENAI_ROLE_USER, "content": prompt}],
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
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


def parse_openai_compatible_response_payload(response: requests.Response) -> tuple[str, TokenMetrics]:
    try:
        payload = response.json()
    except ValueError as error:
        raise ProviderResponseError(f"Invalid JSON response payload: {error}") from error
    if not isinstance(payload, dict):
        raise ProviderResponseError("Invalid response payload type")

    token_metrics = parse_openai_token_metrics(payload)
    text = _openai_compatible_content(payload)
    return text, token_metrics


def _openai_compatible_content(payload: dict[str, object]) -> str:
    choices = payload.get(OPENAI_CHOICES_FIELD)
    if not isinstance(choices, list) or not choices:
        raise ProviderResponseError("Missing choices in response payload")
    message = _openai_compatible_message(choices[0])
    raw_content = message.get(OPENAI_CONTENT_FIELD)
    if raw_content is None:
        raise ProviderResponseError("Missing message content in response payload")
    if not isinstance(raw_content, str):
        raise ProviderResponseError("Invalid message content type in response payload")
    text = raw_content.strip()
    if not text:
        raise ProviderResponseError("Empty response payload")
    return text


def _openai_compatible_message(choice: object) -> dict[str, object]:
    first_choice = choice
    if not isinstance(first_choice, dict):
        raise ProviderResponseError("Invalid choice type in response payload")
    message = first_choice.get(OPENAI_MESSAGE_FIELD)
    if not isinstance(message, dict):
        raise ProviderResponseError("Missing message in response payload")
    return message
