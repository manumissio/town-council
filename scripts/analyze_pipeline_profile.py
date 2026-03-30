#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROM_LINE = re.compile(r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>-?[0-9]+(?:\.[0-9]+)?)$')
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze pipeline profiling artifacts and rank bottlenecks.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", default="experiments/results/profiling")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = Path(args.output_dir)
    run_dir = output_root / args.run_id if output_root.name != args.run_id else output_root
    summary = rank_bottlenecks(run_dir)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "top_bottlenecks.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "summary": str(run_dir / 'summary.json')}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
