from __future__ import annotations

from pipeline import metrics_definitions, metrics_redis_backend
from pipeline.metrics_provider_keys import histogram_bucket_label, provider_base_labels_key, provider_labels_key


def mirror_histogram(
    metric_prefix: str,
    labels_key: str,
    value: float,
    buckets: tuple[float, ...],
) -> None:
    bucket_key = f"{metric_prefix}:bucket:{labels_key}"
    meta_key = f"{metric_prefix}:meta:{labels_key}"
    metrics_redis_backend._redis_hincrby(bucket_key, histogram_bucket_label(value, buckets), 1)
    metrics_redis_backend._redis_hincrby(meta_key, "count", 1)
    metrics_redis_backend._redis_hincrbyfloat(meta_key, "sum", float(value))


def record_provider_request(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    duration_ms: float,
) -> None:
    metrics_definitions.PROVIDER_REQUESTS_TOTAL.labels(
        provider=provider,
        operation=operation,
        model=model,
        outcome=outcome,
    ).inc()
    metrics_definitions.PROVIDER_REQUEST_DURATION_MS.labels(
        provider=provider,
        operation=operation,
        model=model,
        outcome=outcome,
    ).observe(
        max(0.0, duration_ms)
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    metrics_redis_backend._redis_incr(f"tc:provider:req_total:{labels_key}", 1)


def record_provider_ttft(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    ttft_ms: float,
) -> None:
    observed_ttft_ms = max(0.0, ttft_ms)
    metrics_definitions.PROVIDER_TTFT_MS.labels(
        provider=provider,
        operation=operation,
        model=model,
        outcome=outcome,
    ).observe(
        observed_ttft_ms
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    mirror_histogram(
        "tc:provider:ttft_ms",
        labels_key,
        float(observed_ttft_ms),
        metrics_definitions.TTFT_BUCKETS,
    )


def record_provider_tokens_per_sec(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    tokens_per_sec: float,
) -> None:
    observed_tokens_per_sec = max(0.0, tokens_per_sec)
    metrics_definitions.PROVIDER_TOKENS_PER_SEC.labels(
        provider=provider,
        operation=operation,
        model=model,
        outcome=outcome,
    ).observe(
        observed_tokens_per_sec
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    mirror_histogram(
        "tc:provider:tps",
        labels_key,
        float(observed_tokens_per_sec),
        metrics_definitions.TPS_BUCKETS,
    )


def record_provider_token_counts(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    observed_prompt_tokens = max(0, int(prompt_tokens))
    observed_completion_tokens = max(0, int(completion_tokens))
    metrics_definitions.PROVIDER_PROMPT_TOKENS_TOTAL.labels(
        provider=provider,
        operation=operation,
        model=model,
        outcome=outcome,
    ).inc(
        observed_prompt_tokens
    )
    metrics_definitions.PROVIDER_COMPLETION_TOKENS_TOTAL.labels(
        provider=provider,
        operation=operation,
        model=model,
        outcome=outcome,
    ).inc(
        observed_completion_tokens
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    metrics_redis_backend._redis_incr(
        f"tc:provider:prompt_tokens_total:{labels_key}",
        observed_prompt_tokens,
    )
    metrics_redis_backend._redis_incr(
        f"tc:provider:completion_tokens_total:{labels_key}",
        observed_completion_tokens,
    )


def record_provider_timeout(
    provider: str,
    operation: str,
    model: str,
) -> None:
    metrics_definitions.PROVIDER_TIMEOUTS_TOTAL.labels(
        provider=provider,
        operation=operation,
        model=model,
    ).inc()
    base_key = provider_base_labels_key(provider, operation, model)
    metrics_redis_backend._redis_incr(f"tc:provider:timeouts_total:{base_key}", 1)


def record_provider_retry(
    provider: str,
    operation: str,
    model: str,
) -> None:
    metrics_definitions.PROVIDER_RETRIES_TOTAL.labels(
        provider=provider,
        operation=operation,
        model=model,
    ).inc()
    base_key = provider_base_labels_key(provider, operation, model)
    metrics_redis_backend._redis_incr(f"tc:provider:retries_total:{base_key}", 1)
