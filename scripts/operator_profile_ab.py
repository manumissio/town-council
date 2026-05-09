from __future__ import annotations

import math
from statistics import median


DEFAULT_GATES = {
    "section_compliance_improvement_pp": 5.0,
    "fallback_increase_pp_max": 1.0,
    "grounding_drop_pp_max": 1.0,
    "manual_review_median_improvement_min": 0.5,
    "summary_p95_increase_pct_max": 25.0,
    "segment_p95_increase_pct_max": 25.0,
    "failure_rate_increase_pp_max": 1.0,
    "queue_wait_p95_minutes_max": 10.0,
    "search_p95_regression_pct_max": 15.0,
}

PROFILE_KEYS = (
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_PROFILE",
    "LOCAL_AI_HTTP_MODEL",
    "WORKER_CONCURRENCY",
    "WORKER_POOL",
    "OLLAMA_NUM_PARALLEL",
)


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def p95(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, int(math.ceil(0.95 * len(ordered))) - 1)
    return float(ordered[idx])


def aggregate_arm(rows):
    total = len(rows)
    if total == 0:
        return {
            "n": 0,
            "section_compliance_rate": 0.0,
            "fallback_rate": 0.0,
            "grounding_rate": 0.0,
            "failure_rate": 0.0,
            "summary_p95_s": 0.0,
            "segment_p95_s": 0.0,
            "partial_disclosure_rate": 0.0,
            "ttft_median_ms": 0.0,
            "ttft_p95_ms": 0.0,
            "ttft_n": 0,
            "tokens_per_sec_median": 0.0,
            "tokens_per_sec_n": 0,
            "prompt_tokens_total": 0,
            "completion_tokens_total": 0,
            "total_tokens_total": 0,
        }

    section = sum(1 for r in rows if to_bool(r.get("section_compliance_pass"))) / total
    fallback = sum(1 for r in rows if to_bool(r.get("fallback_used"))) / total
    grounding = sum(1 for r in rows if to_bool(r.get("grounding_pass"))) / total
    failed = sum(1 for r in rows if to_bool(r.get("task_failed"))) / total
    partial = sum(1 for r in rows if to_bool(r.get("partial_coverage_disclosed"))) / total

    summary_p95 = p95([to_float(r.get("summary_duration_s")) for r in rows])
    segment_p95 = p95([to_float(r.get("segment_duration_s")) for r in rows])
    ttft_values = [to_float(r.get("ttft_ms")) for r in rows if to_float(r.get("ttft_ms")) > 0]
    tps_values = [to_float(r.get("tokens_per_sec")) for r in rows if to_float(r.get("tokens_per_sec")) > 0]
    prompt_tokens_total = sum(int(to_float(r.get("prompt_tokens"), 0.0)) for r in rows)
    completion_tokens_total = sum(int(to_float(r.get("completion_tokens"), 0.0)) for r in rows)
    total_tokens_total = sum(int(to_float(r.get("total_tokens"), 0.0)) for r in rows)

    return {
        "n": total,
        "section_compliance_rate": section,
        "fallback_rate": fallback,
        "grounding_rate": grounding,
        "failure_rate": failed,
        "summary_p95_s": summary_p95,
        "segment_p95_s": segment_p95,
        "partial_disclosure_rate": partial,
        "ttft_median_ms": float(median(ttft_values)) if ttft_values else 0.0,
        "ttft_p95_ms": p95(ttft_values) if ttft_values else 0.0,
        "ttft_n": len(ttft_values),
        "tokens_per_sec_median": float(median(tps_values)) if tps_values else 0.0,
        "tokens_per_sec_n": len(tps_values),
        "prompt_tokens_total": prompt_tokens_total,
        "completion_tokens_total": completion_tokens_total,
        "total_tokens_total": total_tokens_total,
    }


def compare_arms(control, treatment, gates=None):
    gates = gates or DEFAULT_GATES
    c = lambda k, d=0.0: float(control.get(k, d))
    t = lambda k, d=0.0: float(treatment.get(k, d))

    def pct(v):
        return float(v) * 100.0

    deltas = {
        "section_compliance_pp": pct(t("section_compliance_rate") - c("section_compliance_rate")),
        "fallback_pp": pct(t("fallback_rate") - c("fallback_rate")),
        "grounding_pp": pct(t("grounding_rate") - c("grounding_rate")),
        "failure_rate_pp": pct(t("failure_rate") - c("failure_rate")),
        "summary_p95_pct": ((t("summary_p95_s") - c("summary_p95_s")) / c("summary_p95_s") * 100.0) if c("summary_p95_s") else 0.0,
        "segment_p95_pct": ((t("segment_p95_s") - c("segment_p95_s")) / c("segment_p95_s") * 100.0) if c("segment_p95_s") else 0.0,
        "ttft_median_ms_delta": t("ttft_median_ms") - c("ttft_median_ms"),
        "ttft_p95_ms_delta": t("ttft_p95_ms") - c("ttft_p95_ms"),
        "tokens_per_sec_median_delta": t("tokens_per_sec_median") - c("tokens_per_sec_median"),
        "prompt_tokens_total_delta": t("prompt_tokens_total") - c("prompt_tokens_total"),
        "completion_tokens_total_delta": t("completion_tokens_total") - c("completion_tokens_total"),
        "total_tokens_total_delta": t("total_tokens_total") - c("total_tokens_total"),
    }

    checks = {
        "section_compliance": deltas["section_compliance_pp"] >= gates["section_compliance_improvement_pp"],
        "fallback": deltas["fallback_pp"] <= gates["fallback_increase_pp_max"],
        "grounding": deltas["grounding_pp"] >= -gates["grounding_drop_pp_max"],
        "summary_p95": deltas["summary_p95_pct"] <= gates["summary_p95_increase_pct_max"],
        "segment_p95": deltas["segment_p95_pct"] <= gates["segment_p95_increase_pct_max"],
        "failure_rate": deltas["failure_rate_pp"] <= gates["failure_rate_increase_pp_max"],
    }

    return {
        "deltas": deltas,
        "checks": checks,
        "all_pass": all(checks.values()),
    }


def arm_metadata(rows, configs):
    by_arm = {}
    for arm in ("A", "B"):
        arm_rows = [row for row in rows if str(row.get("arm") or "").strip().upper() == arm]
        models = sorted({str(row.get("model") or "").strip() for row in arm_rows if str(row.get("model") or "").strip()})
        config = next((cfg for cfg in configs if str(cfg.get("arm") or "").strip().upper() == arm), {})
        profile = config.get("profile") if isinstance(config.get("profile"), dict) else {}
        by_arm[arm] = {
            "run_id": config.get("run_id"),
            "model": models[0] if len(models) == 1 else (models or [config.get("model") or "unknown"])[0],
            "models_seen": models or ([str(config.get("model"))] if config.get("model") else []),
            "profile": {key: profile.get(key) for key in PROFILE_KEYS if profile.get(key) not in (None, "")},
        }
    return by_arm


def render_report(control, treatment, comparison, run_ids, arm_metadata):
    lines = []
    lines.append("# A/B Report v1")
    lines.append("")
    lines.append(f"Runs: {', '.join(run_ids)}")
    lines.append("")
    lines.append("## Arm Identity")
    lines.append("")
    lines.append("| Arm | Run ID | Model | Runtime Profile |")
    lines.append("|---|---|---|---|")
    for arm in ("A", "B"):
        meta = arm_metadata.get(arm) or {}
        profile = meta.get("profile") or {}
        profile_text = ", ".join(f"{key}={value}" for key, value in profile.items()) or "-"
        label = "Control (A)" if arm == "A" else "Treatment (B)"
        lines.append(f"| {label} | {meta.get('run_id') or '-'} | {meta.get('model') or '-'} | {profile_text} |")
    lines.append("")
    lines.append("## Arm Metrics")
    lines.append("")
    lines.append("| Metric | Control (A) | Treatment (B) |")
    lines.append("|---|---:|---:|")
    rows = [
        ("N", control["n"], treatment["n"]),
        ("Section compliance %", control["section_compliance_rate"] * 100, treatment["section_compliance_rate"] * 100),
        ("Fallback used %", control["fallback_rate"] * 100, treatment["fallback_rate"] * 100),
        ("Grounding pass %", control["grounding_rate"] * 100, treatment["grounding_rate"] * 100),
        ("Failure rate %", control["failure_rate"] * 100, treatment["failure_rate"] * 100),
        ("Summary p95 (s)", control["summary_p95_s"], treatment["summary_p95_s"]),
        ("Segment p95 (s)", control["segment_p95_s"], treatment["segment_p95_s"]),
        ("TTFT median (ms)", control["ttft_median_ms"], treatment["ttft_median_ms"]),
        ("TTFT p95 (ms)", control["ttft_p95_ms"], treatment["ttft_p95_ms"]),
        ("TTFT sample count", control["ttft_n"], treatment["ttft_n"]),
        ("TPS median", control["tokens_per_sec_median"], treatment["tokens_per_sec_median"]),
        ("TPS sample count", control["tokens_per_sec_n"], treatment["tokens_per_sec_n"]),
        ("Prompt tokens total", control["prompt_tokens_total"], treatment["prompt_tokens_total"]),
        ("Completion tokens total", control["completion_tokens_total"], treatment["completion_tokens_total"]),
        ("Total tokens total", control["total_tokens_total"], treatment["total_tokens_total"]),
    ]
    for name, a, b in rows:
        lines.append(f"| {name} | {a:.2f} | {b:.2f} |" if isinstance(a, float) or isinstance(b, float) else f"| {name} | {a} | {b} |")

    lines.append("")
    lines.append("## Gate Evaluation")
    lines.append("")
    for key, passed in comparison["checks"].items():
        lines.append(f"- {key}: {'PASS' if passed else 'FAIL'}")
    for key, passed in comparison.get("extra_checks", {}).items():
        lines.append(f"- {key}: {'PASS' if passed else 'FAIL'}")
    lines.append(f"- overall: {'PASS' if comparison['all_pass'] else 'FAIL'}")
    lines.append("")
    lines.append("## Deltas (B - A)")
    lines.append("")
    for key, value in comparison["deltas"].items():
        lines.append(f"- {key}: {value:.2f}")
    if comparison.get("manual_review_median_delta") is not None:
        lines.append(f"- manual_review_median_delta: {comparison['manual_review_median_delta']:.2f}")

    return "\n".join(lines) + "\n"
