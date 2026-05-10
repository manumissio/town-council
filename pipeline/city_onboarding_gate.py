from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pipeline.city_onboarding_metrics import CityMetrics
from pipeline.rollout_registry import RolloutEntry, load_rollout_entry


class RolloutLoader(Protocol):
    def __call__(self, city_slug: str) -> RolloutEntry: ...


def safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def evaluate_city(
    city: str,
    metrics: CityMetrics,
    *,
    rollout_loader: RolloutLoader = load_rollout_entry,
) -> dict[str, Any]:
    rollout_entry = rollout_loader(city)
    crawl_success_rate = safe_rate(metrics.crawl_success_count, metrics.run_count)
    extraction_non_empty_rate = safe_rate(
        metrics.run_window_extraction_non_empty_count,
        metrics.run_window_catalog_total,
    )
    segmentation_complete_empty_rate = safe_rate(
        metrics.run_window_segmentation_complete_empty_count,
        metrics.run_window_agenda_catalog_total,
    )
    segmentation_failed_rate = safe_rate(
        metrics.run_window_segmentation_failed_count,
        metrics.run_window_agenda_catalog_total,
    )

    insufficient_data = (
        metrics.run_count <= 0
        or metrics.run_window_catalog_total <= 0
        or metrics.run_window_agenda_catalog_total <= 0
    )

    stable_noop_confirmation = (
        rollout_entry.stable_noop_eligible == "yes"
        and rollout_entry.last_fresh_pass_run_id != ""
        and metrics.run_count > 0
        and metrics.stable_noop_run_count == metrics.run_count
        and metrics.run_window_catalog_total == 0
        and metrics.run_window_agenda_catalog_total == 0
    )

    gates = {
        "crawl_success_rate_gte_95pct": bool(crawl_success_rate is not None and crawl_success_rate >= 0.95),
        "non_empty_extraction_rate_gte_90pct": bool(
            extraction_non_empty_rate is not None and extraction_non_empty_rate >= 0.90
        ),
        "segmentation_complete_empty_rate_gte_95pct": bool(
            segmentation_complete_empty_rate is not None and segmentation_complete_empty_rate >= 0.95
        ),
        "segmentation_failed_rate_lt_5pct": bool(
            segmentation_failed_rate is not None and segmentation_failed_rate < 0.05
        ),
        "searchability_smoke_pass": bool(metrics.search_success_count == metrics.run_count and metrics.run_count > 0),
    }

    failed_gates = [name for name, passed in gates.items() if not passed]
    if stable_noop_confirmation:
        failed_gates = []
        quality_gate = "pass"
        quality_gate_reason = f"stable_delta_noop:{rollout_entry.last_fresh_pass_run_id}"
    else:
        quality_gate = (
            "pass" if (not insufficient_data and not failed_gates) else "insufficient_data" if insufficient_data else "fail"
        )
        quality_gate_reason = (
            "fresh_evidence" if quality_gate == "pass" else "insufficient_data" if insufficient_data else "failed_gates"
        )

    return {
        "city": city,
        "run_count": metrics.run_count,
        "crawl_success_count": metrics.crawl_success_count,
        "search_success_count": metrics.search_success_count,
        "catalog_total": metrics.catalog_total,
        "agenda_catalog_total": metrics.agenda_catalog_total,
        "extraction_non_empty_count": metrics.extraction_non_empty_count,
        "segmentation_complete_empty_count": metrics.segmentation_complete_empty_count,
        "segmentation_failed_count": metrics.segmentation_failed_count,
        "run_window_catalog_total": metrics.run_window_catalog_total,
        "run_window_agenda_catalog_total": metrics.run_window_agenda_catalog_total,
        "run_window_extraction_non_empty_count": metrics.run_window_extraction_non_empty_count,
        "run_window_segmentation_complete_empty_count": metrics.run_window_segmentation_complete_empty_count,
        "run_window_segmentation_failed_count": metrics.run_window_segmentation_failed_count,
        "crawl_success_rate": crawl_success_rate,
        "extraction_non_empty_rate": extraction_non_empty_rate,
        "segmentation_complete_empty_rate": segmentation_complete_empty_rate,
        "segmentation_failed_rate": segmentation_failed_rate,
        "gates": gates,
        "failed_gates": failed_gates,
        "quality_gate": quality_gate,
        "quality_gate_reason": quality_gate_reason,
        "stable_noop_run_count": metrics.stable_noop_run_count,
    }


def write_markdown(path: Path, run_id: str, results: list[dict[str, Any]]) -> None:
    lines = [
        "# City Onboarding Gate Evaluation",
        "",
        f"run_id: `{run_id}`",
        "",
        "| city | quality_gate | reason | run_window_catalog_total | historical_catalog_total | crawl_success_rate | extraction_non_empty_rate | segmentation_complete_empty_rate | segmentation_failed_rate | failed_gates |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            "| {city} | {quality_gate} | {quality_gate_reason} | {run_window_catalog_total} | {catalog_total} | {crawl_success_rate} | {extraction_non_empty_rate} | {segmentation_complete_empty_rate} | {segmentation_failed_rate} | {failed_gates} |".format(
                city=row["city"],
                quality_gate=row["quality_gate"],
                quality_gate_reason=row["quality_gate_reason"],
                run_window_catalog_total=row["run_window_catalog_total"],
                catalog_total=row["catalog_total"],
                crawl_success_rate="-" if row["crawl_success_rate"] is None else f"{row['crawl_success_rate']:.3f}",
                extraction_non_empty_rate=(
                    "-" if row["extraction_non_empty_rate"] is None else f"{row['extraction_non_empty_rate']:.3f}"
                ),
                segmentation_complete_empty_rate=(
                    "-"
                    if row["segmentation_complete_empty_rate"] is None
                    else f"{row['segmentation_complete_empty_rate']:.3f}"
                ),
                segmentation_failed_rate=(
                    "-" if row["segmentation_failed_rate"] is None else f"{row['segmentation_failed_rate']:.3f}"
                ),
                failed_gates=", ".join(row["failed_gates"]) if row["failed_gates"] else "-",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
