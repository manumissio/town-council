from __future__ import annotations

import re
from typing import Any


PROM_LINE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+"
    r"(?P<value>-?[0-9]+(?:\.[0-9]+)?)$"
)


def parse_labels(label_text: str | None) -> dict[str, str]:
    if not label_text:
        return {}
    parsed_labels: dict[str, str] = {}
    for raw_part in label_text.split(","):
        label_part = raw_part.strip()
        if not label_part or "=" not in label_part:
            continue
        label_key, label_value = label_part.split("=", 1)
        parsed_labels[label_key.strip()] = label_value.strip().strip('"')
    return parsed_labels


def parse_metrics(raw_metrics: str) -> list[dict[str, Any]]:
    metric_rows: list[dict[str, Any]] = []
    for raw_line in raw_metrics.splitlines():
        metric_line = raw_line.strip()
        if not metric_line or metric_line.startswith("#"):
            continue
        metric_match = PROM_LINE.match(metric_line)
        if not metric_match:
            continue
        metric_rows.append(
            {
                "name": metric_match.group("name"),
                "labels": parse_labels(metric_match.group("labels")),
                "value": float(metric_match.group("value")),
            }
        )
    return metric_rows


def sum_metric(metric_rows: list[dict[str, Any]], metric_name: str, labels: dict[str, str] | None = None) -> float:
    total_value = 0.0
    for metric_row in metric_rows:
        if metric_row["name"] != metric_name:
            continue
        if labels and any(metric_row["labels"].get(label_key) != expected for label_key, expected in labels.items()):
            continue
        total_value += float(metric_row["value"])
    return total_value
