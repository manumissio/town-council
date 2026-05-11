from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from pipeline.db_session import db_session
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_quality import is_summary_grounded


REQUIRED_SECTIONS = [
    "bluf:",
    "why this matters:",
    "top actions:",
    "potential impacts:",
    "unknowns:",
]

AB_RESULT_FIELDNAMES = [
    "run_id",
    "arm",
    "model",
    "catalog_id",
    "doc_kind",
    "status",
    "segment_duration_s",
    "summary_duration_s",
    "task_failed",
    "agenda_items_count",
    "summary_chars",
    "summary_text",
    "section_compliance_pass",
    "grounding_pass",
    "fallback_used",
    "partial_coverage_disclosed",
    "ttft_ms",
    "tokens_per_sec",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_eval_duration_ms",
    "eval_duration_ms",
]


def load_task_phase_rows(tasks_path: Path) -> tuple[dict[tuple[int, str], dict[str, Any]], str | None]:
    by_catalog_phase: dict[tuple[int, str], dict[str, Any]] = {}
    arm: str | None = None
    with tasks_path.open("r", encoding="utf-8") as task_file:
        for raw_line in task_file:
            line = raw_line.strip()
            if not line:
                continue
            task_row = json.loads(line)
            catalog_id = int(task_row["catalog_id"])
            phase = str(task_row.get("phase") or "")
            by_catalog_phase[(catalog_id, phase)] = task_row
            arm = arm or task_row.get("arm")
    return by_catalog_phase, arm


def collect_ab_rows(
    *,
    run_id: str,
    arm: str | None,
    by_catalog_phase: dict[tuple[int, str], dict[str, Any]],
    run_config: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    catalog_ids = sorted({catalog_id for catalog_id, _ in by_catalog_phase})
    with db_session() as db:
        for catalog_id in catalog_ids:
            catalog = db.get(Catalog, catalog_id)
            if catalog is None:
                continue
            rows.append(_catalog_ab_row(db, run_id, arm, catalog, by_catalog_phase, run_config))
    return rows


def _catalog_ab_row(
    db: Any,
    run_id: str,
    arm: str | None,
    catalog: Catalog,
    by_catalog_phase: dict[tuple[int, str], dict[str, Any]],
    run_config: dict[str, Any],
) -> dict[str, Any]:
    catalog_id = int(catalog.id)
    doc_kind, agenda_items = _catalog_context(db, catalog_id)
    segment_row = by_catalog_phase.get((catalog_id, "segment"), {})
    summarize_row = by_catalog_phase.get((catalog_id, "summarize"), {})
    summary_text = _summary_text_from_sources(catalog=catalog, summarize_row=summarize_row)
    source_text = _source_text_for_grounding(catalog, doc_kind, agenda_items)
    telemetry_source = summarize_row if summarize_row else segment_row
    any_failed = bool(segment_row.get("task_failed")) or bool(summarize_row.get("task_failed"))
    return {
        "run_id": run_id,
        "arm": arm or "",
        "model": str(summarize_row.get("model") or segment_row.get("model") or run_config.get("model") or ""),
        "catalog_id": catalog_id,
        "doc_kind": doc_kind,
        "status": "failed" if any_failed else "complete",
        **_duration_payload(segment_row, summarize_row),
        "task_failed": any_failed,
        "agenda_items_count": len(agenda_items),
        **_summary_quality_payload(summary_text, source_text),
        **_telemetry_payload(telemetry_source),
    }


def _catalog_context(db: Any, catalog_id: int) -> tuple[str, list[AgendaItem]]:
    document = db.query(Document).filter(Document.catalog_id == catalog_id).first()
    doc_kind = (document.category or "unknown") if document else "unknown"
    agenda_items = db.query(AgendaItem).filter(AgendaItem.catalog_id == catalog_id).order_by(AgendaItem.order).all()
    return doc_kind, agenda_items


def _duration_payload(segment_row: dict[str, Any], summarize_row: dict[str, Any]) -> dict[str, float]:
    return {
        "segment_duration_s": float(segment_row.get("duration_s") or 0.0),
        "summary_duration_s": float(summarize_row.get("duration_s") or 0.0),
    }


def _summary_quality_payload(summary_text: str, source_text: str) -> dict[str, Any]:
    grounding = is_summary_grounded(summary_text, source_text)
    return {
        "summary_chars": len(summary_text),
        "summary_text": summary_text,
        "section_compliance_pass": _section_compliance(summary_text),
        "grounding_pass": bool(grounding.is_grounded),
        "fallback_used": _detect_fallback(summary_text),
        "partial_coverage_disclosed": _detect_partial_coverage(summary_text),
    }


def _telemetry_payload(telemetry_source: dict[str, Any]) -> dict[str, float | int | None]:
    return {
        "ttft_ms": _to_float(_provider_metric_from_phase_row(telemetry_source, "ttft_ms")),
        "tokens_per_sec": _to_float(_provider_metric_from_phase_row(telemetry_source, "tokens_per_sec")),
        **_token_metrics(telemetry_source),
        "prompt_eval_duration_ms": _to_float(_provider_metric_from_phase_row(telemetry_source, "prompt_eval_duration_ms")),
        "eval_duration_ms": _to_float(_provider_metric_from_phase_row(telemetry_source, "eval_duration_ms")),
    }


def _source_text_for_grounding(catalog: Catalog, doc_kind: str, agenda_items: list[AgendaItem]) -> str:
    if doc_kind != "agenda":
        return catalog.content or ""
    return "\n".join(
        " | ".join(
            [
                (agenda_item.title or "").strip(),
                (agenda_item.description or "").strip(),
                (agenda_item.classification or "").strip(),
                (agenda_item.result or "").strip(),
            ]
        ).strip(" | ")
        for agenda_item in agenda_items
    )


def _token_metrics(telemetry_source: dict[str, Any]) -> dict[str, int | None]:
    prompt_tokens = _to_int(_provider_metric_from_phase_row(telemetry_source, "prompt_tokens"))
    completion_tokens = _to_int(_provider_metric_from_phase_row(telemetry_source, "completion_tokens"))
    total_tokens = _to_int(_provider_metric_from_phase_row(telemetry_source, "total_tokens"))
    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def write_ab_outputs(run_dir: Path, rows: list[dict[str, Any]]) -> tuple[Path, Path]:
    csv_path = run_dir / "ab_rows.csv"
    json_path = run_dir / "ab_rows.json"
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=AB_RESULT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump(rows, json_file, indent=2)
    return csv_path, json_path


def _section_compliance(summary: str) -> bool:
    text = (summary or "").lower()
    return all(marker in text for marker in REQUIRED_SECTIONS)


def _detect_fallback(summary: str) -> bool:
    text = (summary or "").lower()
    return "no substantive actions were retained after filtering" in text or "agenda summary unavailable" in text


def _detect_partial_coverage(summary: str) -> bool:
    text = (summary or "").lower()
    patterns = (r"partial coverage", r"included\s+\d+\s+of\s+\d+\s+items", r"first\s+\d+\s+of\s+\d+")
    return any(re.search(pattern, text) for pattern in patterns)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _summary_text_from_sources(*, catalog: Catalog, summarize_row: dict[str, Any]) -> str:
    task_result = summarize_row.get("task_result")
    if isinstance(task_result, dict):
        summary = task_result.get("summary")
        if isinstance(summary, str):
            return summary.strip()
    if summarize_row.get("task_failed"):
        return ""
    return (catalog.summary or "").strip()


def _provider_metric_from_phase_row(row: dict[str, Any], metric_name: str) -> Any:
    direct = row.get(metric_name)
    if direct not in (None, ""):
        return direct
    task_result = row.get("task_result")
    candidates = []
    if isinstance(task_result, dict):
        candidates.append(task_result)
        for key in ("telemetry", "provider_metrics", "metrics"):
            nested = task_result.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
    for candidate in candidates:
        value = candidate.get(metric_name)
        if value not in (None, ""):
            return value
    return None
