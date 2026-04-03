#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROM_LINE = re.compile(r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>-?[0-9]+(?:\.[0-9]+)?)$')
SUMMARY_HYDRATION_LINE = re.compile(
    r"summary_hydration_backfill .*agenda_deterministic_complete=(?P<agenda>\d+)"
    r".*llm_complete=(?P<llm>\d+)"
    r".*deterministic_fallback_complete=(?P<fallback>\d+)"
)
KEY_VALUE_TOKEN = re.compile(r"(?P<key>[a-zA-Z_]+)=(?P<value>[^\s]+)")
TOTAL_ELAPSED_TOLERANCE_PCT = 20.0
PHASE_DURATION_TOLERANCE_PCT = 25.0
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


def _parse_labels(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    out = {}
    for part in text.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def _parse_metrics(raw: str) -> list[dict[str, Any]]:
    rows = []
    for line in raw.splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        match = PROM_LINE.match(item)
        if not match:
            continue
        rows.append(
            {
                "name": match.group("name"),
                "labels": _parse_labels(match.group("labels")),
                "value": float(match.group("value")),
            }
        )
    return rows


def _sum_metric(rows: list[dict[str, Any]], name: str, labels: dict[str, str] | None = None) -> float:
    total = 0.0
    for row in rows:
        if row["name"] != name:
            continue
        if labels and any(row["labels"].get(key) != expected for key, expected in labels.items()):
            continue
        total += float(row["value"])
    return total


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


def _load_summary_hydration_counts(run_dir: Path) -> dict[str, int]:
    latest = _load_latest_counter_line(run_dir, "summary_hydration_backfill")
    if latest:
        return latest
    commands_log = run_dir / "commands.log"
    if not commands_log.exists():
        return {}
    fallback: dict[str, int] = {}
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


def _coerce_counter_value(raw: str) -> int | str:
    value = raw.strip().rstrip(",")
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _load_latest_counter_line(run_dir: Path, prefix: str) -> dict[str, int | str]:
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
            match.group("key"): _coerce_counter_value(match.group("value"))
            for match in KEY_VALUE_TOKEN.finditer(line)
        }
        if counters:
            latest = counters
    return latest


def _classify_summary_phase(
    *,
    contribution_pct: float,
    queue_wait_s: float,
    execution_s: float,
    summary_counts: dict[str, int],
) -> tuple[str, float]:
    if queue_wait_s > 0 and queue_wait_s >= max(1.0, execution_s * 0.5):
        return "queueing", 0.0
    llm_complete = int(summary_counts.get("llm_complete") or 0)
    deterministic_fallback_complete = int(summary_counts.get("deterministic_fallback_complete") or 0)
    agenda_deterministic_complete = int(summary_counts.get("agenda_deterministic_complete") or 0)
    if llm_complete > 0 or deterministic_fallback_complete > 0:
        return "inference/provider", float(llm_complete + deterministic_fallback_complete)
    if agenda_deterministic_complete > 0:
        return "CPU/parsing", 0.0
    return _classify_bottleneck("summarize", contribution_pct, queue_wait_s, execution_s), 0.0


def _aggregate_phase_rows(spans: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, float]] = {}
    for row in spans:
        phase = str(row.get("phase") or "")
        if phase not in LEAF_PHASES:
            continue
        bucket = totals.setdefault(
            phase,
            {
                "duration_s": 0.0,
                "task_duration_s": 0.0,
                "queue_wait_s": 0.0,
                "count": 0.0,
                "components": set(),
                "durations": [],
            },
        )
        duration_s = float(row.get("duration_s") or 0.0)
        component = str(row.get("component") or "unknown")
        if row.get("event_type") == "task_span":
            bucket["task_duration_s"] += duration_s
            bucket["queue_wait_s"] += float(row.get("queue_wait_s") or 0.0)
        elif row.get("event_type") == "span":
            bucket["duration_s"] += duration_s
        bucket["count"] += 1.0
        bucket["components"].add(component)
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
    totals = result.get("totals") if isinstance(result.get("totals"), dict) else {}
    combined_total = float(totals.get("combined_elapsed_seconds") or 0.0)
    if combined_total > 0:
        return combined_total, None

    derived_total, notes = _derived_total_from_spans(spans)
    if derived_total > 0:
        note = None
        if not result:
            note = "result_missing"
        elif not combined_total:
            note = f"derived_total_from_{'+'.join(notes)}"
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

    total_elapsed_s, total_note = _select_total_elapsed_seconds(result, spans)
    phase_totals = _aggregate_phase_rows(spans)
    ranked = []
    for phase, stats in sorted(phase_totals.items(), key=lambda item: item[1]["duration_s"], reverse=True):
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
                "provider_metrics_present": bool(day_summary.get("provider_metrics_present")),
                "provider_requests_total": provider_requests,
                "occurrence_count": int(stats["count"]),
                "components": sorted(str(item) for item in stats["components"]),
                "durations": list(stats["durations"]),
            }
        )

    top_three = ranked[:3]
    confidence = "ok"
    if not spans:
        confidence = "reduced-confidence:no_spans"
    elif not day_summary.get("provider_metrics_present"):
        confidence = f"reduced-confidence:{day_summary.get('provider_metrics_reason') or 'provider_metrics_missing'}"
    elif total_note is not None:
        confidence = f"reduced-confidence:{total_note}"
    elif total_elapsed_s > 0 and ranked and ranked[0]["contribution_pct"] > 100.0:
        confidence = "reduced-confidence:inconsistent_totals"

    return {
        "run_id": manifest.get("run_id"),
        "mode": manifest.get("mode"),
        "catalog_count": manifest.get("catalog_count"),
        "baseline_valid": bool(manifest.get("baseline_valid")),
        "elapsed_seconds": round(float(total_elapsed_s), 3),
        "confidence": confidence,
        "elapsed_source": total_note or "result_totals",
        "top_bottlenecks": top_three,
        "all_phases": ranked,
    }


def _load_expected_baseline(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not payload:
        raise ValueError(f"baseline expectation missing or invalid: {path}")
    required = {"manifest_name", "baseline_valid", "elapsed_seconds", "top_phases", "stable_counters"}
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"baseline expectation missing required keys: {', '.join(missing)}")
    if not isinstance(payload.get("top_phases"), list):
        raise ValueError("baseline expectation top_phases must be a list")
    if not isinstance(payload.get("stable_counters"), dict):
        raise ValueError("baseline expectation stable_counters must be an object")
    return payload


def _compare_timing_metric(name: str, expected: float, actual: float, tolerance_pct: float) -> dict[str, Any]:
    allowed = round(float(expected) * (tolerance_pct / 100.0), 3)
    delta = round(float(actual) - float(expected), 3)
    passed = float(actual) <= float(expected) + allowed
    return {
        "metric": name,
        "expected": round(float(expected), 3),
        "actual": round(float(actual), 3),
        "delta": delta,
        "tolerance_pct": tolerance_pct,
        "tolerance_abs": allowed,
        "status": "pass" if passed else "fail",
        "reason": "timing_regression" if not passed else "within_tolerance",
    }


def _compare_exact_metric(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    passed = actual == expected
    return {
        "metric": name,
        "expected": expected,
        "actual": actual,
        "status": "pass" if passed else "fail",
        "reason": "workload_shape_drift" if not passed else "match",
    }


def compare_against_expected_baseline(run_dir: Path, summary: dict[str, Any], expected_path: Path) -> dict[str, Any]:
    expected = _load_expected_baseline(expected_path)
    result: dict[str, Any] = {
        "expected_baseline": str(expected_path),
        "manifest_name": expected.get("manifest_name"),
        "status": "pass",
        "reason": "matched",
        "comparable": True,
        "checks": [],
    }
    if not summary.get("baseline_valid"):
        result.update({"status": "non_comparable", "reason": "baseline_invalid", "comparable": False})
        return result
    if str(summary.get("confidence") or "").startswith("reduced-confidence"):
        result.update({"status": "non_comparable", "reason": "confidence_reduced", "comparable": False})
        return result

    checks: list[dict[str, Any]] = []
    checks.append(
        _compare_timing_metric(
            "elapsed_seconds",
            float(expected["elapsed_seconds"]),
            float(summary.get("elapsed_seconds") or 0.0),
            TOTAL_ELAPSED_TOLERANCE_PCT,
        )
    )

    actual_phases = {str(item.get("phase")): item for item in summary.get("all_phases") or []}
    for phase_entry in expected.get("top_phases") or []:
        phase = str(phase_entry.get("phase") or "")
        actual = actual_phases.get(phase)
        if actual is None:
            checks.append(
                {
                    "metric": f"phase.{phase}",
                    "expected": round(float(phase_entry.get("duration_s") or 0.0), 3),
                    "actual": None,
                    "status": "fail",
                    "reason": "artifact_missing",
                }
            )
            continue
        checks.append(
            _compare_timing_metric(
                f"phase.{phase}.duration_s",
                float(phase_entry.get("duration_s") or 0.0),
                float(actual.get("duration_s") or 0.0),
                PHASE_DURATION_TOLERANCE_PCT,
            )
        )

    for counter_name, expected_counter_values in sorted((expected.get("stable_counters") or {}).items()):
        actual_counter_values = _load_latest_counter_line(run_dir, counter_name)
        if not actual_counter_values:
            checks.append(
                {
                    "metric": f"{counter_name}.__present__",
                    "expected": True,
                    "actual": False,
                    "status": "fail",
                    "reason": "artifact_missing",
                }
            )
            continue
        for key, expected_value in sorted((expected_counter_values or {}).items()):
            checks.append(
                _compare_exact_metric(
                    f"{counter_name}.{key}",
                    expected_value,
                    actual_counter_values.get(key),
                )
            )

    result["checks"] = checks
    failures = [check for check in checks if check.get("status") == "fail"]
    if failures:
        result["status"] = "fail"
        result["reason"] = str(failures[0].get("reason") or "regression")
        result["failed_checks"] = failures
    return result


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# Pipeline Profile: {summary.get('run_id')}",
        "",
        f"- mode: `{summary.get('mode')}`",
        f"- catalog_count: `{summary.get('catalog_count')}`",
        f"- elapsed_seconds: `{summary.get('elapsed_seconds')}`",
        f"- confidence: `{summary.get('confidence')}`",
        "",
        "## Top 3 Bottlenecks",
    ]
    for index, item in enumerate(summary.get("top_bottlenecks") or [], start=1):
        lines.extend(
            [
                f"{index}. `{item['phase']}`",
                f"   - classification: `{item['classification']}`",
                f"   - wall_clock_s: `{item['duration_s']}`",
                f"   - contribution_pct: `{item['contribution_pct']}`",
                f"   - queue_wait_s: `{item['queue_wait_s']}`",
                f"   - task_duration_s: `{item['task_duration_s']}`",
                f"   - occurrence_count: `{item['occurrence_count']}`",
            ]
        )
    return "\n".join(lines) + "\n"


def render_compare_report(summary: dict[str, Any], comparison: dict[str, Any]) -> str:
    lines = [
        f"# Baseline Compare: {summary.get('run_id')}",
        "",
        f"- expected_baseline: `{comparison.get('expected_baseline')}`",
        f"- status: `{comparison.get('status')}`",
        f"- reason: `{comparison.get('reason')}`",
        f"- comparable: `{comparison.get('comparable')}`",
        "",
        "## Checks",
    ]
    for check in comparison.get("checks") or []:
        lines.append(f"- `{check['metric']}`: `{check['status']}` expected=`{check.get('expected')}` actual=`{check.get('actual')}`")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze pipeline profiling artifacts and rank bottlenecks.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", default="experiments/results/profiling")
    parser.add_argument("--compare-to", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = Path(args.output_dir)
    run_dir = output_root / args.run_id if output_root.name != args.run_id else output_root
    summary = rank_bottlenecks(run_dir)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "top_bottlenecks.md").write_text(render_report(summary), encoding="utf-8")
    payload: dict[str, Any] = {"run_id": args.run_id, "summary": str(run_dir / "summary.json")}
    if args.compare_to:
        comparison = compare_against_expected_baseline(run_dir, summary, Path(args.compare_to))
        (run_dir / "baseline_compare.json").write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "baseline_compare.md").write_text(render_compare_report(summary, comparison), encoding="utf-8")
        payload["baseline_compare"] = str(run_dir / "baseline_compare.json")
        print(json.dumps(payload, indent=2))
        return 0 if comparison.get("status") == "pass" else 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
