from __future__ import annotations

from collections.abc import Callable
import sys

from pipeline import metrics_definitions
from pipeline.metrics_provider_keys import histogram_bucket_label, provider_base_labels_key, provider_labels_key

RedisIncrement = Callable[[str, int], None]
RedisHashIncrement = Callable[[str, str, int], None]
RedisHashFloatIncrement = Callable[[str, str, float], None]


def _facade_metric(metric_name: str) -> object:
    metrics_facade = sys.modules.get("pipeline.metrics")
    return getattr(metrics_facade, metric_name, getattr(metrics_definitions, metric_name))


def mirror_histogram(
    metric_prefix: str,
    labels_key: str,
    value: float,
    buckets: tuple[float, ...],
    *,
    redis_hincrby: RedisHashIncrement,
    redis_hincrbyfloat: RedisHashFloatIncrement,
) -> None:
    bucket_key = f"{metric_prefix}:bucket:{labels_key}"
    meta_key = f"{metric_prefix}:meta:{labels_key}"
    redis_hincrby(bucket_key, histogram_bucket_label(value, buckets), 1)
    redis_hincrby(meta_key, "count", 1)
    redis_hincrbyfloat(meta_key, "sum", float(value))


def record_provider_request(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    duration_ms: float,
    *,
    redis_incr: RedisIncrement,
) -> None:
    _facade_metric("PROVIDER_REQUESTS_TOTAL").labels(provider=provider, operation=operation, model=model, outcome=outcome).inc()
    _facade_metric("PROVIDER_REQUEST_DURATION_MS").labels(provider=provider, operation=operation, model=model, outcome=outcome).observe(
        max(0.0, duration_ms)
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    redis_incr(f"tc:provider:req_total:{labels_key}", 1)


def record_provider_ttft(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    ttft_ms: float,
    *,
    redis_hincrby: RedisHashIncrement,
    redis_hincrbyfloat: RedisHashFloatIncrement,
) -> None:
    observed_ttft_ms = max(0.0, ttft_ms)
    _facade_metric("PROVIDER_TTFT_MS").labels(provider=provider, operation=operation, model=model, outcome=outcome).observe(
        observed_ttft_ms
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    mirror_histogram(
        "tc:provider:ttft_ms",
        labels_key,
        float(observed_ttft_ms),
        metrics_definitions.TTFT_BUCKETS,
        redis_hincrby=redis_hincrby,
        redis_hincrbyfloat=redis_hincrbyfloat,
    )


def record_provider_tokens_per_sec(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    tokens_per_sec: float,
    *,
    redis_hincrby: RedisHashIncrement,
    redis_hincrbyfloat: RedisHashFloatIncrement,
) -> None:
    observed_tokens_per_sec = max(0.0, tokens_per_sec)
    _facade_metric("PROVIDER_TOKENS_PER_SEC").labels(provider=provider, operation=operation, model=model, outcome=outcome).observe(
        observed_tokens_per_sec
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    mirror_histogram(
        "tc:provider:tps",
        labels_key,
        float(observed_tokens_per_sec),
        metrics_definitions.TPS_BUCKETS,
        redis_hincrby=redis_hincrby,
        redis_hincrbyfloat=redis_hincrbyfloat,
    )


def record_provider_token_counts(
    provider: str,
    operation: str,
    model: str,
    outcome: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    redis_incr: RedisIncrement,
) -> None:
    observed_prompt_tokens = max(0, int(prompt_tokens))
    observed_completion_tokens = max(0, int(completion_tokens))
    _facade_metric("PROVIDER_PROMPT_TOKENS_TOTAL").labels(provider=provider, operation=operation, model=model, outcome=outcome).inc(
        observed_prompt_tokens
    )
    _facade_metric("PROVIDER_COMPLETION_TOKENS_TOTAL").labels(provider=provider, operation=operation, model=model, outcome=outcome).inc(
        observed_completion_tokens
    )
    labels_key = provider_labels_key(provider, operation, model, outcome)
    redis_incr(f"tc:provider:prompt_tokens_total:{labels_key}", observed_prompt_tokens)
    redis_incr(f"tc:provider:completion_tokens_total:{labels_key}", observed_completion_tokens)


def record_provider_timeout(
    provider: str,
    operation: str,
    model: str,
    *,
    redis_incr: RedisIncrement,
) -> None:
    _facade_metric("PROVIDER_TIMEOUTS_TOTAL").labels(provider=provider, operation=operation, model=model).inc()
    base_key = provider_base_labels_key(provider, operation, model)
    redis_incr(f"tc:provider:timeouts_total:{base_key}", 1)


def record_provider_retry(
    provider: str,
    operation: str,
    model: str,
    *,
    redis_incr: RedisIncrement,
) -> None:
    _facade_metric("PROVIDER_RETRIES_TOTAL").labels(provider=provider, operation=operation, model=model).inc()
    base_key = provider_base_labels_key(provider, operation, model)
    redis_incr(f"tc:provider:retries_total:{base_key}", 1)
