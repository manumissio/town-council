from __future__ import annotations

import logging

from pipeline.provider_telemetry import (
    ProviderAttemptTelemetry,
    ProviderRetryTelemetry,
    ProviderTelemetryIdentity,
    record_provider_attempt_event,
    record_provider_retry_event,
    record_provider_timeout_event,
)


def log_provider_policy(
    logger: logging.Logger,
    identity: ProviderTelemetryIdentity,
    *,
    operation: str,
    timeout_seconds: int,
    max_retries: int,
) -> None:
    logger.info(
        "provider_policy provider=%s api=%s model=%s profile=%s operation=%s timeout_s=%s retry_budget=%s",
        identity.provider_name,
        identity.api_name,
        identity.model_name,
        identity.profile_name,
        operation,
        timeout_seconds,
        max_retries,
    )


def record_retry(
    logger: logging.Logger,
    identity: ProviderTelemetryIdentity,
    retry_telemetry: ProviderRetryTelemetry,
) -> None:
    record_provider_retry_event(logger, identity, retry_telemetry)


def record_attempt(
    logger: logging.Logger,
    identity: ProviderTelemetryIdentity,
    attempt_telemetry: ProviderAttemptTelemetry,
) -> None:
    record_provider_attempt_event(logger, identity, attempt_telemetry)


def record_timeout(provider_name: str, operation: str, model_name: str) -> None:
    record_provider_timeout_event(provider_name, operation, model_name)
