from __future__ import annotations

import math
from urllib.parse import quote, unquote


def encode_provider_label(value: str) -> str:
    return quote(str(value), safe="")


def decode_provider_label(value: str) -> str:
    return unquote(value)


def provider_labels_key(provider: str, operation: str, model: str, outcome: str) -> str:
    return ":".join(
        (
            encode_provider_label(provider),
            encode_provider_label(operation),
            encode_provider_label(model),
            encode_provider_label(outcome),
        )
    )


def provider_base_labels_key(provider: str, operation: str, model: str) -> str:
    return ":".join((encode_provider_label(provider), encode_provider_label(operation), encode_provider_label(model)))


def split_labels_key(labels_key: str, expected_parts: int) -> tuple[str, ...] | None:
    parts = labels_key.split(":")
    if len(parts) != expected_parts:
        return None
    return tuple(decode_provider_label(part) for part in parts)


def histogram_bucket_label(value: float, buckets: tuple[float, ...]) -> str:
    for upper_bound in buckets:
        if value <= upper_bound:
            if math.isinf(upper_bound):
                return "+Inf"
            return str(float(upper_bound))
    return "+Inf"
