from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Iterator, Literal, Protocol, Sequence, TypeVar


PROFILE_RUN_ID_ENV = "TC_PROFILE_RUN_ID"
PROFILE_MODE_ENV = "TC_PROFILE_MODE"
PROFILE_ARTIFACT_DIR_ENV = "TC_PROFILE_ARTIFACT_DIR"
PROFILE_CATALOG_MANIFEST_ENV = "TC_PROFILE_CATALOG_MANIFEST"
PROFILE_WORKLOAD_ONLY_ENV = "TC_PROFILE_WORKLOAD_ONLY"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SELECTED_IDS_CACHE: tuple[str | None, set[int] | None] = (None, None)
_OBSERVER_DEPTH: ContextVar[int] = ContextVar("profile_observer_depth", default=0)
_OBSERVER_SECONDS: ContextVar[float] = ContextVar("profile_observer_seconds", default=0.0)
QueryT = TypeVar("QueryT", bound="CatalogScopedQuery")
EligibilityBoundary = Literal["before", "after"]
EligibilitySubject = Literal["catalog", "event", "place"]


@dataclass(frozen=True, slots=True)
class ProfileSpanContext:
    phase: str
    component: str
    catalog_id: int | None
    started_at: str
    started_perf: float
    observer_at_start: float


class CatalogIdPredicate(Protocol):
    def in_(self, values: Sequence[int]) -> object: ...


class CatalogScopedQuery(Protocol):
    # Keep the typing local to profiling so callers do not need SQLAlchemy-specific imports.
    def filter(self: QueryT, _criterion: object) -> QueryT: ...


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
    if manifest_path is None or not manifest_path.is_file():
        raise FileNotFoundError(f"profile catalog manifest does not exist: {manifest_key}")
    ids: set[int] = set()
    for line_number, raw_line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            ids.add(int(line))
        except ValueError as error:
            raise ValueError(
                f"invalid catalog id in profile manifest {manifest_path} at line {line_number}: {line!r}"
            ) from error
    if not ids:
        raise ValueError(f"profile catalog manifest contains no catalog ids: {manifest_path}")
    _SELECTED_IDS_CACHE = (manifest_key, ids)
    return ids


def apply_catalog_id_scope(query: QueryT, catalog_id_column: CatalogIdPredicate) -> QueryT:
    ids = selected_catalog_ids()
    if ids is None:
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
        "timestamp": utc_now_iso(),
        **payload,
    }
    append_jsonl(artifact_dir / "spans.jsonl", body)


def append_phase_eligibility(
    *,
    phase: str,
    boundary: EligibilityBoundary,
    subject: EligibilitySubject,
    eligible_ids: Sequence[int],
) -> None:
    with profile_observer():
        normalized_ids = sorted({int(eligible_id) for eligible_id in eligible_ids})
        append_profile_event(
            {
                "event_type": "phase_eligibility",
                "phase": phase,
                "boundary": boundary,
                "subject": subject,
                "eligible_ids": normalized_ids,
                "eligible_count": len(normalized_ids),
            }
        )


def observer_seconds() -> float:
    return _OBSERVER_SECONDS.get()


@contextmanager
def profile_observer() -> Iterator[None]:
    depth = _OBSERVER_DEPTH.get()
    depth_token = _OBSERVER_DEPTH.set(depth + 1)
    started_perf = time.perf_counter() if depth == 0 else None
    try:
        yield
    finally:
        _OBSERVER_DEPTH.reset(depth_token)
        if started_perf is not None:
            _OBSERVER_SECONDS.set(observer_seconds() + time.perf_counter() - started_perf)


def workload_duration_seconds(started_perf: float, observer_at_start: float) -> float:
    elapsed_seconds = time.perf_counter() - started_perf
    observer_overhead_seconds = observer_seconds() - observer_at_start
    return max(0.0, elapsed_seconds - observer_overhead_seconds)


def _append_span_event(
    *,
    span_context: ProfileSpanContext,
    outcome: str,
    span_metadata: dict[str, Any],
) -> None:
    observer_overhead_seconds = observer_seconds() - span_context.observer_at_start
    span_metadata["observer_overhead_s"] = round(observer_overhead_seconds, 6)
    span_event = {
        "event_type": "span",
        "phase": span_context.phase,
        "component": span_context.component,
        "catalog_id": span_context.catalog_id,
        "started_at": span_context.started_at,
        "finished_at": utc_now_iso(),
        "duration_s": round(
            workload_duration_seconds(
                span_context.started_perf,
                span_context.observer_at_start,
            ),
            6,
        ),
        "outcome": outcome,
        "metadata": span_metadata or None,
    }
    with profile_observer():
        append_profile_event(span_event)


@contextmanager
def profile_span(
    *,
    phase: str,
    component: str,
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    catalog_id: int | None = None,
) -> Iterator[dict[str, Any]]:
    span_context = ProfileSpanContext(
        phase=phase,
        component=component,
        catalog_id=catalog_id,
        started_at=utc_now_iso(),
        started_perf=time.perf_counter(),
        observer_at_start=observer_seconds(),
    )
    span_meta: dict[str, Any] = dict(metadata or {})
    try:
        yield span_meta
    except Exception:
        _append_span_event(
            span_context=span_context,
            outcome="failure",
            span_metadata=span_meta,
        )
        raise
    _append_span_event(
        span_context=span_context,
        outcome=outcome,
        span_metadata=span_meta,
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
