from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Iterator


PROFILE_RUN_ID_ENV = "TC_PROFILE_RUN_ID"
PROFILE_MODE_ENV = "TC_PROFILE_MODE"
PROFILE_ARTIFACT_DIR_ENV = "TC_PROFILE_ARTIFACT_DIR"
PROFILE_BASELINE_VALID_ENV = "TC_PROFILE_BASELINE_VALID"
PROFILE_CATALOG_MANIFEST_ENV = "TC_PROFILE_CATALOG_MANIFEST"
PROFILE_WORKLOAD_ONLY_ENV = "TC_PROFILE_WORKLOAD_ONLY"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SELECTED_IDS_CACHE: tuple[str | None, set[int] | None] = (None, None)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(raw_value: str | None) -> Path | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path


def profiling_enabled() -> bool:
    return bool(current_run_id() and current_artifact_dir())


def current_run_id() -> str | None:
    value = str(os.getenv(PROFILE_RUN_ID_ENV, "") or "").strip()
    return value or None


def current_mode() -> str:
    value = str(os.getenv(PROFILE_MODE_ENV, "") or "").strip().lower()
    return value if value in {"triage", "baseline"} else "triage"


def baseline_valid() -> bool:
    return str(os.getenv(PROFILE_BASELINE_VALID_ENV, "") or "").strip().lower() in {"1", "true", "yes"}


def workload_only_profile() -> bool:
    return str(os.getenv(PROFILE_WORKLOAD_ONLY_ENV, "") or "").strip().lower() in {"1", "true", "yes"}


def current_artifact_dir() -> Path | None:
    return _resolve_path(os.getenv(PROFILE_ARTIFACT_DIR_ENV))


def selected_catalog_ids() -> set[int] | None:
    global _SELECTED_IDS_CACHE
    manifest_key = str(os.getenv(PROFILE_CATALOG_MANIFEST_ENV, "") or "").strip()
    if not manifest_key:
        _SELECTED_IDS_CACHE = (None, None)
        return None
    cached_key, cached_ids = _SELECTED_IDS_CACHE
    if cached_key == manifest_key:
        return cached_ids

    manifest_path = _resolve_path(manifest_key)
    ids: set[int] = set()
    if manifest_path and manifest_path.exists():
        for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            try:
                ids.add(int(line))
            except ValueError:
                continue
    resolved = ids or None
    _SELECTED_IDS_CACHE = (manifest_key, resolved)
    return resolved


def apply_catalog_id_scope(query, catalog_id_column):
    ids = selected_catalog_ids()
    if not ids:
        return query
    return query.filter(catalog_id_column.in_(sorted(ids)))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def append_profile_event(payload: dict[str, Any]) -> None:
    artifact_dir = current_artifact_dir()
    run_id = current_run_id()
    if artifact_dir is None or not run_id:
        return
    body = {
        "run_id": run_id,
        "mode": current_mode(),
        "baseline_valid": baseline_valid(),
        "timestamp": utc_now_iso(),
        **payload,
    }
    append_jsonl(artifact_dir / "spans.jsonl", body)


@contextmanager
def profile_span(
    *,
    phase: str,
    component: str,
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    catalog_id: int | None = None,
) -> Iterator[dict[str, Any]]:
    started_at = utc_now_iso()
    started_perf = time.perf_counter()
    span_meta: dict[str, Any] = dict(metadata or {})
    try:
        yield span_meta
    except Exception:
        append_profile_event(
            {
                "event_type": "span",
                "phase": phase,
                "component": component,
                "catalog_id": catalog_id,
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "duration_s": round(time.perf_counter() - started_perf, 6),
                "outcome": "failure",
                "metadata": span_meta or None,
            }
        )
        raise
    append_profile_event(
        {
            "event_type": "span",
            "phase": phase,
            "component": component,
            "catalog_id": catalog_id,
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "duration_s": round(time.perf_counter() - started_perf, 6),
            "outcome": outcome,
            "metadata": span_meta or None,
        }
    )


def phase_from_task_name(task_name: str) -> str:
    mapping = {
        "pipeline.tasks.generate_summary_task": "summarize",
        "pipeline.tasks.segment_agenda_task": "segment_agenda",
        "pipeline.tasks.extract_votes_task": "extract_votes",
        "pipeline.tasks.extract_text_task": "extract_text",
        "enrichment.generate_topics": "topic_modeling",
        "semantic.embed_catalog": "semantic_embed",
    }
    return mapping.get(str(task_name or ""), str(task_name or "unknown"))
