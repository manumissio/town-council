from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, cast

from scripts.operator_profile_reports import AGENDA_SUMMARY_SUBPHASE_KEYS
from scripts.operator_profile_reports import load_expected_baseline
from scripts.operator_prometheus import parse_metrics as _parse_metrics
from scripts.operator_prometheus import sum_metric as _sum_metric


SUMMARY_HYDRATION_LINE = re.compile(
    r"summary_hydration_backfill .*agenda_deterministic_complete=(?P<agenda>\d+)"
    r".*llm_complete=(?P<llm>\d+)"
    r".*deterministic_fallback_complete=(?P<fallback>\d+)"
)
KEY_VALUE_TOKEN = re.compile(r"(?P<key>[a-zA-Z_]+)=(?P<value>[^\s]+)")
LEAF_PHASES = {
    "db_migrate",
    "seed_places",
    "promote_stage",
    "download",
    "extract_parallel",
    "segment_agenda",
    "summarize",
    "index_search",
    "entity_backfill",
    "table_extraction",
    "org_backfill",
    "topic_modeling",
    "people_linking",
    "semantic_embed",
}
CounterValue = int | str
PhaseStats = dict[str, Any]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _classify_bottleneck(phase: str, contribution_pct: float, queue_wait_s: float, execution_s: float) -> str:
    if queue_wait_s > 0 and queue_wait_s >= max(1.0, execution_s * 0.5):
        return "queueing"
    if phase in {"summarize", "segment_agenda", "topic_modeling", "semantic_embed"}:
        return "inference/provider"
    if phase in {"table_extraction", "entity_backfill", "people_linking"}:
        return "CPU/parsing"
    if phase in {"db_migrate", "seed_places", "promote_stage", "org_backfill", "index_search"}:
        return "database/indexing"
    if contribution_pct >= 25.0:
        return "orchestration/serialization"
    return "orchestration/serialization"


def _coerce_counter_value(raw: str) -> int | str:
    value = raw.strip().rstrip(",")
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _safe_int_counter(counter_values: Mapping[str, CounterValue], key: str) -> int:
    raw_value = counter_values.get(key, 0)
    if isinstance(raw_value, int):
        return raw_value
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return 0


def _load_latest_counter_line(run_dir: Path, prefix: str) -> dict[str, CounterValue]:
    commands_log = run_dir / "commands.log"
    if not commands_log.exists():
        return {}
    latest: dict[str, int | str] = {}
    for line in commands_log.read_text(encoding="utf-8").splitlines():
        if prefix not in line:
            continue
        if not re.search(rf"\b{re.escape(prefix)}\b", line):
            continue
        counters = {
            match.group("key"): _coerce_counter_value(match.group("value")) for match in KEY_VALUE_TOKEN.finditer(line)
        }
        if counters:
            latest = counters
    return latest


def _load_summary_hydration_counts(run_dir: Path) -> dict[str, CounterValue]:
    latest = _load_latest_counter_line(run_dir, "summary_hydration_backfill")
    if latest:
        return latest
    commands_log = run_dir / "commands.log"
    if not commands_log.exists():
        return {}
    fallback: dict[str, CounterValue] = {}
    for line in commands_log.read_text(encoding="utf-8").splitlines():
        match = SUMMARY_HYDRATION_LINE.search(line)
        if not match:
            continue
        fallback = {
            "agenda_deterministic_complete": int(match.group("agenda")),
            "llm_complete": int(match.group("llm")),
            "deterministic_fallback_complete": int(match.group("fallback")),
        }
    return fallback


def _classify_summary_phase(
    *,
    contribution_pct: float,
    queue_wait_s: float,
    execution_s: float,
    summary_counts: Mapping[str, CounterValue],
) -> tuple[str, float]:
    if queue_wait_s > 0 and queue_wait_s >= max(1.0, execution_s * 0.5):
        return "queueing", 0.0
    llm_complete = _safe_int_counter(summary_counts, "llm_complete")
    deterministic_fallback_complete = _safe_int_counter(summary_counts, "deterministic_fallback_complete")
    agenda_deterministic_complete = _safe_int_counter(summary_counts, "agenda_deterministic_complete")
    if llm_complete > 0 or deterministic_fallback_complete > 0:
        return "inference/provider", float(llm_complete + deterministic_fallback_complete)
    if agenda_deterministic_complete > 0:
        return "CPU/parsing", 0.0
    return _classify_bottleneck("summarize", contribution_pct, queue_wait_s, execution_s), 0.0


def _extract_summary_subphase_timings(summary_counts: Mapping[str, CounterValue]) -> dict[str, int]:
    return {metric_name: _safe_int_counter(summary_counts, metric_name) for metric_name in AGENDA_SUMMARY_SUBPHASE_KEYS}


def _aggregate_phase_rows(spans: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    totals: dict[str, PhaseStats] = {}
    for row in spans:
        if row.get("event_type") not in {"span", "task_span"}:
            continue
        phase = str(row.get("phase") or "")
        if phase not in LEAF_PHASES:
            continue
        bucket = totals.setdefault(
            phase,
            {"duration_s": 0.0, "task_duration_s": 0.0, "queue_wait_s": 0.0, "count": 0.0, "components": set(), "durations": []},
        )
        duration_s = float(row.get("duration_s") or 0.0)
        if row.get("event_type") == "task_span":
            bucket["task_duration_s"] += duration_s
            bucket["queue_wait_s"] += float(row.get("queue_wait_s") or 0.0)
        elif row.get("event_type") == "span":
            bucket["duration_s"] += duration_s
        bucket["count"] += 1.0
        bucket["components"].add(str(row.get("component") or "unknown"))
        bucket["durations"].append(round(duration_s, 6))
    return totals


def _unfinished_task_attempts(spans: list[dict[str, Any]]) -> set[str]:
    started_attempts = {
        str(row.get("execution_id"))
        for row in spans
        if row.get("event_type") == "task_start" and row.get("execution_id")
    }
    finished_attempts = {
        str(row.get("execution_id"))
        for row in spans
        if row.get("event_type") == "task_span" and row.get("execution_id")
    }
    return started_attempts - finished_attempts


def _task_evidence_confidence_reasons(spans: list[dict[str, Any]]) -> list[str]:
    confidence_reasons: list[str] = []
    if _unfinished_task_attempts(spans):
        confidence_reasons.append("unfinished_task_attempt")
    if any(
        row.get("event_type") in {"task_start", "task_span"}
        and "retry_ordinal" in row
        and row.get("retry_ordinal") is None
        for row in spans
    ):
        confidence_reasons.append("unknown_task_retry_ordinal")
    dispatch_counts = Counter(
        (
            str(row.get("task_id")),
            row.get("retry_ordinal"),
            str(row.get("boundary")),
        )
        for row in spans
        if row.get("event_type") == "task_dispatch" and row.get("task_id")
    )
    dispatch_attempts = {(task_id, retry_ordinal) for task_id, retry_ordinal, _boundary in dispatch_counts}
    if any(
        dispatch_counts[(task_id, retry_ordinal, "before")]
        != dispatch_counts[(task_id, retry_ordinal, "after")]
        for task_id, retry_ordinal in dispatch_attempts
    ):
        confidence_reasons.append("unmatched_task_dispatch")
    completed_dispatches = {
        (task_id, retry_ordinal)
        for task_id, retry_ordinal in dispatch_attempts
        if dispatch_counts[(task_id, retry_ordinal, "before")] > 0
        and dispatch_counts[(task_id, retry_ordinal, "before")]
        == dispatch_counts[(task_id, retry_ordinal, "after")]
    }
    if any(
        row.get("event_type") in {"task_start", "task_span"}
        and isinstance(row.get("retry_ordinal"), int)
        and row.get("retry_ordinal", 0) > 0
        and (str(row.get("task_id")), row.get("retry_ordinal")) not in completed_dispatches
        for row in spans
    ):
        confidence_reasons.append("missing_retry_dispatch")
    return confidence_reasons


def _total_span_duration(spans: list[dict[str, Any]], phase: str) -> float:
    return next(
        (
            float(row.get("duration_s") or 0.0)
            for row in spans
            if row.get("event_type") == "span"
            and row.get("phase") == phase
            and row.get("outcome") == "success"
            and isinstance(row.get("metadata"), dict)
            and "observer_overhead_s" in row["metadata"]
        ),
        0.0,
    )


def _resolve_include_batch(
    manifest: dict[str, Any],
    run_result: dict[str, Any],
) -> tuple[bool, list[str]]:
    manifest_include_batch = manifest.get("include_batch")
    if not isinstance(manifest_include_batch, bool):
        return False, ["include_batch_manifest_invalid"]
    include_batch = manifest_include_batch
    if "include_batch" not in run_result:
        return include_batch, []
    run_result_include_batch = run_result.get("include_batch")
    if isinstance(run_result_include_batch, bool) and run_result_include_batch == include_batch:
        return include_batch, []
    return include_batch, ["include_batch_mismatch"]


def _select_total_elapsed_seconds(
    result: dict[str, Any],
    spans: list[dict[str, Any]],
    *,
    include_batch: bool,
) -> tuple[float, str, list[str]]:
    required_phases = ["pipeline_total"]
    if include_batch:
        required_phases.append("batch_enrichment_total")
    corrected_totals = {phase: _total_span_duration(spans, phase) for phase in required_phases}
    missing_total_reasons = [
        f"missing_corrected_total:{phase}"
        for phase, duration in corrected_totals.items()
        if duration <= 0
    ]
    if not missing_total_reasons:
        confidence_reasons = [] if result else ["result_missing"]
        return sum(corrected_totals.values()), "corrected_total_spans", confidence_reasons

    raw_totals = result.get("totals")
    totals: dict[str, Any] = raw_totals if isinstance(raw_totals, dict) else {}
    combined_total = float(totals.get("combined_elapsed_seconds") or 0.0)
    if combined_total > 0:
        return combined_total, "raw_result_totals", missing_total_reasons
    fallback = float(result.get("elapsed_seconds") or 0.0)
    if fallback > 0:
        return fallback, "raw_elapsed_seconds", missing_total_reasons
    if not result:
        return 0.0, "no_total_elapsed_time", ["result_missing", *missing_total_reasons]
    return 0.0, "no_total_elapsed_time", missing_total_reasons


def rank_bottlenecks(run_dir: Path) -> dict[str, Any]:
    manifest = _load_json(run_dir / "run_manifest.json")
    result = _load_json(run_dir / "result.json")
    day_summary = _load_json(run_dir / "day_summary.json")
    spans = _load_jsonl(run_dir / "spans.jsonl")
    worker_metrics_raw = (run_dir / "worker_metrics.prom").read_text(encoding="utf-8") if (run_dir / "worker_metrics.prom").exists() else ""
    worker_rows = _parse_metrics(worker_metrics_raw)
    summary_hydration_counts = _load_summary_hydration_counts(run_dir)
    provider_metrics_present = bool(day_summary.get("provider_metrics_present")) if isinstance(day_summary, dict) else False
    provider_metrics_reason = str(day_summary.get("provider_metrics_reason") or "provider_metrics_missing") if isinstance(day_summary, dict) else "provider_metrics_missing"
    include_batch, include_batch_confidence_reasons = _resolve_include_batch(
        manifest,
        result,
    )
    total_elapsed_s, elapsed_source, total_confidence_reasons = _select_total_elapsed_seconds(
        result,
        spans,
        include_batch=include_batch,
    )
    ranked = []
    for phase, stats in sorted(_aggregate_phase_rows(spans).items(), key=lambda item: item[1]["duration_s"], reverse=True):
        duration_s = float(stats["duration_s"])
        contribution_pct = (duration_s / total_elapsed_s * 100.0) if total_elapsed_s > 0 else 0.0
        queue_wait_s = float(stats["queue_wait_s"])
        task_duration_s = float(stats["task_duration_s"])
        classification = _classify_bottleneck(phase, contribution_pct, queue_wait_s, task_duration_s)
        provider_requests = _sum_metric(worker_rows, "tc_provider_requests_total")
        if phase == "summarize":
            classification, provider_requests = _classify_summary_phase(
                contribution_pct=contribution_pct,
                queue_wait_s=queue_wait_s,
                execution_s=task_duration_s,
                summary_counts=summary_hydration_counts,
            )
        ranked.append(
            {
                "phase": phase,
                "duration_s": round(duration_s, 3),
                "contribution_pct": round(contribution_pct, 2),
                "queue_wait_s": round(queue_wait_s, 3),
                "task_duration_s": round(task_duration_s, 3),
                "classification": classification,
                "provider_metrics_present": provider_metrics_present,
                "provider_requests_total": provider_requests,
                "occurrence_count": int(stats["count"]),
                "components": sorted(str(item) for item in stats["components"]),
                "durations": list(stats["durations"]),
            }
        )
    confidence_reasons: list[str] = []
    if not spans:
        confidence_reasons.append("no_spans")
    if not provider_metrics_present:
        confidence_reasons.append(provider_metrics_reason)
    confidence_reasons.extend(_task_evidence_confidence_reasons(spans))
    confidence_reasons.extend(include_batch_confidence_reasons)
    confidence_reasons.extend(total_confidence_reasons)
    if total_elapsed_s > 0 and ranked and float(cast(Any, ranked[0].get("contribution_pct")) or 0.0) > 100.0:
        confidence_reasons.append("inconsistent_totals")
    confidence = "ok" if not confidence_reasons else f"reduced-confidence:{'+'.join(confidence_reasons)}"
    return {
        "run_id": manifest.get("run_id"),
        "mode": manifest.get("mode"),
        "catalog_count": manifest.get("catalog_count"),
        "baseline_valid": manifest.get("baseline_valid") is True,
        "elapsed_seconds": round(float(total_elapsed_s), 3),
        "confidence": confidence,
        "confidence_reasons": confidence_reasons,
        "elapsed_source": elapsed_source,
        "top_bottlenecks": ranked[:3],
        "all_phases": ranked,
        "summary_hydration_backfill": summary_hydration_counts,
        "summarize_subphase_timings_ms": _extract_summary_subphase_timings(summary_hydration_counts),
    }


def _load_expected_baseline(path: Path) -> dict[str, Any]:
    return load_expected_baseline(path, _load_json)
