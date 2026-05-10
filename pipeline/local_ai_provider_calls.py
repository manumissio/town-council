from __future__ import annotations

from collections.abc import Callable
import logging

from pipeline.llm_provider import ProviderResponseError, ProviderTimeoutError, ProviderUnavailableError


def log_provider_failure(logger: logging.Logger, operation_label: str, error: Exception) -> None:
    logger.error("%s failed: %s", operation_label, error)


def call_provider_text_or_none(
    provider_call: Callable[[], str | None],
    *,
    operation_label: str,
    logger: logging.Logger,
) -> str | None:
    try:
        return provider_call()
    except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as error:
        log_provider_failure(logger, operation_label, error)
        return None
    except Exception as error:
        log_provider_failure(logger, operation_label, error)
        return None
