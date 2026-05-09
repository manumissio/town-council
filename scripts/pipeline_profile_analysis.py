from __future__ import annotations

import json
import re
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


def _derived_total_from_spans(spans: list[dict[str, Any]]) -> tuple[float, list[str]]:
    pipeline_total = next((float(row.get("duration_s") or 0.0) for row in spans if row.get("phase") == "pipeline_total"), 0.0)
    batch_total = next((float(row.get("duration_s") or 0.0) for row in spans if row.get("phase") == "batch_enrichment_total"), 0.0)
    notes = []
    combined = 0.0
    if pipeline_total > 0:
        combined += pipeline_total
        notes.append("pipeline_total")
    if batch_total > 0:
        combined += batch_total
        notes.append("batch_enrichment_total")
    return combined, notes


def _select_total_elapsed_seconds(result: dict[str, Any], spans: list[dict[str, Any]]) -> tuple[float, str | None]:
    raw_totals = result.get("totals")
    totals: dict[str, Any] = raw_totals if isinstance(raw_totals, dict) else {}
    combined_total = float(totals.get("combined_elapsed_seconds") or 0.0)
    if combined_total > 0:
        return combined_total, None
    derived_total, notes = _derived_total_from_spans(spans)
    if derived_total > 0:
        note = "result_missing" if not result else f"derived_total_from_{'+'.join(notes)}"
        return derived_total, note
    fallback = float(result.get("elapsed_seconds") or 0.0)
    if fallback > 0:
        return fallback, "fallback_elapsed_seconds_only"
    return 0.0, "no_total_elapsed_time"


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
    total_elapsed_s, total_note = _select_total_elapsed_seconds(result, spans)
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
    confidence = "ok"
    if not spans:
        confidence = "reduced-confidence:no_spans"
    elif not provider_metrics_present:
        confidence = f"reduced-confidence:{provider_metrics_reason}"
    elif total_note is not None:
        confidence = f"reduced-confidence:{total_note}"
    elif total_elapsed_s > 0 and ranked and float(cast(Any, ranked[0].get("contribution_pct")) or 0.0) > 100.0:
        confidence = "reduced-confidence:inconsistent_totals"
    return {
        "run_id": manifest.get("run_id"),
        "mode": manifest.get("mode"),
        "catalog_count": manifest.get("catalog_count"),
        "baseline_valid": bool(manifest.get("baseline_valid")),
        "elapsed_seconds": round(float(total_elapsed_s), 3),
        "confidence": confidence,
        "elapsed_source": total_note or "result_totals",
        "top_bottlenecks": ranked[:3],
        "all_phases": ranked,
        "summary_hydration_backfill": summary_hydration_counts,
        "summarize_subphase_timings_ms": _extract_summary_subphase_timings(summary_hydration_counts),
    }


def _load_expected_baseline(path: Path) -> dict[str, Any]:
    return load_expected_baseline(path, _load_json)
