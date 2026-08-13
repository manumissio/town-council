from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


from scripts.profile_pipeline_runtime import INFERENCE_PROFILE_KEYS
from scripts.profile_pipeline_runtime import SEMANTIC_PROFILE_KEYS
from scripts.profile_pipeline_runtime import WORKER_PROFILE_KEYS


PROFILE_KEYS = (
    *WORKER_PROFILE_KEYS,
    *INFERENCE_PROFILE_KEYS,
    *SEMANTIC_PROFILE_KEYS,
    "WORKER_PROCESS_COMMAND",
    "SEMANTIC_WORKER_PROCESS_COMMAND",
)
CORE_ELIGIBILITY = (
    ("extract_parallel", "catalog"),
    ("segment_agenda", "catalog"),
    ("summarize", "catalog"),
)
BATCH_ELIGIBILITY = (
    ("entity_backfill", "catalog"),
    ("table_extraction", "catalog"),
    ("org_backfill", "place"),
    ("org_backfill", "event"),
    ("topic_modeling", "catalog"),
)
CORE_SPANS = ("extract_parallel", "segment_agenda", "summarize", "pipeline_total")
BATCH_SPANS = (
    "entity_backfill",
    "table_extraction",
    "org_backfill",
    "topic_modeling",
    "batch_enrichment_total",
)
GATING_PHASES = {
    "segment_agenda",
    "summarize",
    "entity_backfill",
    "table_extraction",
    "org_backfill",
    "topic_modeling",
}
FAILURE_COUNTERS = (
    "failed",
    "error",
    "other",
    "not_generated_yet",
    "embed_dispatch_failed",
    "reindex_failed",
)
COUNTER_TOKEN = re.compile(r"(?P<key>[a-zA-Z_]+)=(?P<value>-?\d+)\b")
EMBED_CATALOG_TASK_NAME = "semantic.embed_catalog"


@dataclass(frozen=True, slots=True)
class BaselineValidation:
    valid: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def _load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, f"artifact_invalid:{path.name}"
    if not isinstance(payload, dict):
        return {}, f"artifact_invalid:{path.name}"
    return payload, None


def load_profile_events(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], f"artifact_invalid:{path.name}"
    for raw_line in raw_lines:
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            return [], f"artifact_invalid:{path.name}"
        if not isinstance(payload, dict):
            return [], f"artifact_invalid:{path.name}"
        rows.append(payload)
    return rows, None


def task_evidence_reasons(
    profile_events: list[dict[str, Any]],
    *,
    require_terminal_dispatches: bool = False,
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if any(
        row.get("event_type") in {"task_dispatch", "task_start", "task_span"}
        and "retry_ordinal" in row
        and row.get("retry_ordinal") is None
        for row in profile_events
    ):
        reasons.add("unknown_task_retry_ordinal")
    completed_dispatches, unmatched_dispatch = _completed_dispatch_attempts(profile_events)
    if unmatched_dispatch:
        reasons.add("unmatched_task_dispatch")
    reasons.update(
        _task_terminal_reasons(
            profile_events,
            completed_dispatches,
            require_terminal_dispatches=require_terminal_dispatches,
        )
    )
    execution_starts = {
        str(row.get("execution_id"))
        for row in profile_events
        if row.get("event_type") == "task_start" and row.get("execution_id")
    }
    execution_terminals = {
        str(row.get("execution_id"))
        for row in profile_events
        if row.get("event_type") == "task_span" and row.get("execution_id")
    }
    if execution_starts - execution_terminals:
        reasons.add("unfinished_task_attempt")
    if execution_terminals - execution_starts:
        reasons.add("orphan_task_terminal")
    started_attempts = {
        (str(row.get("task_id")), row.get("retry_ordinal"))
        for row in profile_events
        if row.get("event_type") == "task_start" and row.get("task_id")
    }
    initial_starts = {attempt for attempt in started_attempts if attempt[1] == 0}
    if initial_starts - completed_dispatches:
        reasons.add("missing_task_dispatch")
    if any(
        row.get("event_type") in {"task_start", "task_span"}
        and isinstance(row.get("retry_ordinal"), int)
        and row.get("retry_ordinal", 0) > 0
        and (str(row.get("task_id")), row.get("retry_ordinal")) not in completed_dispatches
        for row in profile_events
    ):
        reasons.add("missing_retry_dispatch")
    return tuple(sorted(reasons))


def _task_terminal_reasons(
    profile_events: list[dict[str, Any]],
    completed_dispatches: set[tuple[str, Any]],
    *,
    require_terminal_dispatches: bool,
) -> set[str]:
    reasons: set[str] = set()
    started_attempts: set[tuple[str, Any]] = set()
    terminal_attempts: set[tuple[str, Any]] = set()
    task_outcomes: dict[str, list[tuple[object, object]]] = {}
    for profile_event in profile_events:
        task_id = str(profile_event.get("task_id") or "").strip()
        if not task_id:
            continue
        task_attempt = (task_id, profile_event.get("retry_ordinal"))
        if profile_event.get("event_type") == "task_start":
            started_attempts.add(task_attempt)
        elif profile_event.get("event_type") == "task_span":
            terminal_attempts.add(task_attempt)
            task_outcomes.setdefault(task_id, []).append(
                (profile_event.get("retry_ordinal"), profile_event.get("outcome"))
            )
    task_ids = {task_id for task_id, _ in completed_dispatches}
    if require_terminal_dispatches and completed_dispatches - started_attempts:
        reasons.add("task_start_missing")
    if require_terminal_dispatches and completed_dispatches - terminal_attempts:
        reasons.add("task_terminal_missing")
    if any(
        _terminal_task_failed(task_outcomes.get(task_id, []))
        for task_id in task_ids
    ):
        reasons.add("task_terminal_failed")
    return reasons


def _terminal_task_failed(task_attempts: list[tuple[object, object]]) -> bool:
    if not task_attempts:
        return False
    retry_ordinals = [
        retry_ordinal
        for retry_ordinal, _ in task_attempts
        if isinstance(retry_ordinal, int) and not isinstance(retry_ordinal, bool)
    ]
    if not retry_ordinals:
        return True
    latest_retry = max(retry_ordinals)
    return any(outcome != "success" for retry_ordinal, outcome in task_attempts if retry_ordinal == latest_retry)


def _completed_dispatch_attempts(
    profile_events: list[dict[str, Any]],
) -> tuple[set[tuple[str, Any]], bool]:
    outstanding_before: dict[tuple[str, Any], int] = {}
    completed_attempts: set[tuple[str, Any]] = set()
    invalid_attempts: set[tuple[str, Any]] = set()
    for row in profile_events:
        if row.get("event_type") != "task_dispatch" or not row.get("task_id"):
            continue
        attempt = (str(row.get("task_id")), row.get("retry_ordinal"))
        if row.get("boundary") == "before":
            outstanding_before[attempt] = outstanding_before.get(attempt, 0) + 1
        elif row.get("boundary") == "after" and outstanding_before.get(attempt, 0) > 0:
            outstanding_before[attempt] -= 1
            completed_attempts.add(attempt)
        else:
            invalid_attempts.add(attempt)
    invalid_attempts.update(
        attempt for attempt, outstanding_count in outstanding_before.items() if outstanding_count > 0
    )
    return completed_attempts - invalid_attempts, bool(invalid_attempts)


def _phase_evidence(
    profile_events: list[dict[str, Any]],
    *,
    include_batch: bool,
) -> tuple[set[str], set[str]]:
    reasons: set[str] = set()
    warnings: set[str] = set()
    required_eligibility = CORE_ELIGIBILITY + (BATCH_ELIGIBILITY if include_batch else ())
    for phase, subject in required_eligibility:
        matching_rows = [
            row
            for row in profile_events
            if row.get("event_type") == "phase_eligibility"
            and row.get("phase") == phase
            and row.get("subject") == subject
        ]
        boundaries = Counter(str(row.get("boundary")) for row in matching_rows)
        if boundaries != Counter({"before": 1, "after": 1}):
            reasons.add(f"phase_eligibility_incomplete:{phase}:{subject}")
            continue
        after_row = next(row for row in matching_rows if row.get("boundary") == "after")
        eligible_count = after_row.get("eligible_count")
        if not isinstance(eligible_count, int) or isinstance(eligible_count, bool):
            reasons.add(f"phase_eligibility_invalid:{phase}:{subject}")
        elif eligible_count > 0 and phase == "extract_parallel":
            warnings.add("extraction_remainder_nonzero")
        elif eligible_count > 0 and phase in GATING_PHASES:
            reasons.add(f"phase_remainder_nonzero:{phase}:{subject}")
    required_spans = CORE_SPANS + (BATCH_SPANS if include_batch else ())
    for phase in required_spans:
        phase_spans = [
            row
            for row in profile_events
            if row.get("event_type") == "span" and row.get("phase") == phase
        ]
        if len(phase_spans) != 1:
            reasons.add(f"phase_span_incomplete:{phase}")
        elif phase_spans[0].get("outcome") != "success":
            reasons.add(f"phase_span_failed:{phase}")
    return reasons, warnings


def _counter_failure_reasons(commands_log: Path) -> set[str]:
    try:
        lines = commands_log.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return {"artifact_invalid:commands.log"}
    reasons: set[str] = set()
    for line in lines:
        counters = {match.group("key"): int(match.group("value")) for match in COUNTER_TOKEN.finditer(line)}
        for counter_name in reversed(FAILURE_COUNTERS):
            if counters.get(counter_name, 0) > 0:
                reasons.add(f"side_effect_failure:{counter_name}")
                break
    return reasons


def _expected_dispatch_count(commands_log: Path) -> int | None:
    try:
        lines = commands_log.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return None
    for line in reversed(lines):
        if "summary_hydration_backfill" not in line:
            continue
        counters = {match.group("key"): int(match.group("value")) for match in COUNTER_TOKEN.finditer(line)}
        if "embed_enqueued" in counters:
            return counters["embed_enqueued"]
    return 0


def _dispatch_count_reasons(profile_events: list[dict[str, Any]], commands_log: Path) -> set[str]:
    expected_dispatches = _expected_dispatch_count(commands_log)
    if expected_dispatches is None:
        return {"artifact_invalid:commands.log"}
    completed_dispatches, _ = _completed_dispatch_attempts(profile_events)
    dispatch_names: dict[tuple[str, Any], set[str]] = {}
    for profile_event in profile_events:
        if profile_event.get("event_type") != "task_dispatch" or not profile_event.get("task_id"):
            continue
        task_attempt = (str(profile_event["task_id"]), profile_event.get("retry_ordinal"))
        dispatch_names.setdefault(task_attempt, set()).add(str(profile_event.get("task_name") or ""))
    initial_dispatches = sum(
        1
        for task_attempt in completed_dispatches
        if task_attempt[1] == 0 and dispatch_names.get(task_attempt) == {EMBED_CATALOG_TASK_NAME}
    )
    if initial_dispatches < expected_dispatches:
        return {"task_dispatch_count_mismatch"}
    return set()


def _result_reasons(result: dict[str, Any], *, include_batch: bool) -> set[str]:
    reasons: set[str] = set()
    if result.get("status") != "completed" or result.get("error") is not None:
        reasons.add("result_not_completed")
    expected_segments = ["pipeline", *(["pipeline-batch"] if include_batch else [])]
    segments = result.get("segments")
    if not isinstance(segments, list):
        return {"segments_incomplete", *reasons}
    completed_names = [
        str(segment.get("name"))
        for segment in segments
        if isinstance(segment, dict) and segment.get("status") == "completed"
    ]
    if completed_names != expected_segments:
        reasons.add("segments_incomplete")
    return reasons


def _metrics_reasons(day_summary: dict[str, Any]) -> set[str]:
    reasons: set[str] = set()
    delta_keys = (
        "provider_requests_delta_run",
        "provider_timeouts_delta_run",
        "provider_retries_delta_run",
    )
    if day_summary.get("provider_metrics_present") is not True or any(
        not isinstance(day_summary.get(key), int | float) or isinstance(day_summary.get(key), bool)
        for key in delta_keys
    ):
        reasons.add("provider_deltas_incomplete")
    if not isinstance(day_summary.get("search_p95_ms"), int | float) or isinstance(
        day_summary.get("search_p95_ms"), bool
    ):
        reasons.add("search_measurement_missing")
    return reasons


def _provenance_reasons(manifest: dict[str, Any], run_dir: Path) -> set[str]:
    reasons: set[str] = set()
    source_manifest = manifest.get("source_manifest")
    source_sha256 = manifest.get("source_manifest_sha256")
    git_revision = manifest.get("git_commit")
    if (
        not isinstance(source_manifest, str)
        or not source_manifest.startswith("profiling/manifests/")
        or not isinstance(source_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
        or not isinstance(git_revision, str)
        or not git_revision.strip()
        or manifest.get("tracked_tree_clean") is not True
    ):
        reasons.add("source_provenance_incomplete")
    manifest_copy = run_dir / "catalog_manifest.txt"
    try:
        copied_sha256 = hashlib.sha256(manifest_copy.read_bytes()).hexdigest()
    except OSError:
        reasons.add("artifact_invalid:catalog_manifest.txt")
    else:
        if copied_sha256 != source_sha256:
            reasons.add("source_manifest_copy_mismatch")
    return reasons


def validate_profile_artifacts(
    run_dir: Path,
    *,
    expected_run_id: str,
    include_batch: bool,
) -> BaselineValidation:
    manifest, manifest_error = _load_json(run_dir / "run_manifest.json")
    result, result_error = _load_json(run_dir / "result.json")
    day_summary, day_error = _load_json(run_dir / "day_summary.json")
    profile_events, profile_events_error = load_profile_events(run_dir / "spans.jsonl")
    reasons = {error for error in (manifest_error, result_error, day_error, profile_events_error) if error}
    if reasons:
        return BaselineValidation(False, tuple(sorted(reasons)), ())
    artifact_run_ids = {
        str(run_id)
        for run_id in [manifest.get("run_id"), result.get("run_id"), day_summary.get("run_id")]
        if run_id is not None
    }
    artifact_run_ids.update(str(row.get("run_id")) for row in profile_events if row.get("run_id") is not None)
    if artifact_run_ids != {expected_run_id}:
        reasons.add("run_id_mismatch")
    reasons.update(_result_reasons(result, include_batch=include_batch))
    if manifest.get("include_batch") is not include_batch:
        reasons.add("include_batch_mismatch")
    reasons.update(_provenance_reasons(manifest, run_dir))
    phase_reasons, warnings = _phase_evidence(profile_events, include_batch=include_batch)
    reasons.update(phase_reasons)
    reasons.update(task_evidence_reasons(profile_events, require_terminal_dispatches=True))
    reasons.update(_dispatch_count_reasons(profile_events, run_dir / "commands.log"))
    reasons.update(_metrics_reasons(day_summary))
    profile = manifest.get("profile")
    if not isinstance(profile, dict) or any(not str(profile.get(key) or "").strip() for key in PROFILE_KEYS):
        reasons.add("runtime_profile_incomplete")
    elif (
        f"--concurrency={profile['WORKER_CONCURRENCY']}" not in profile["WORKER_PROCESS_COMMAND"]
        or f"--pool={profile['WORKER_POOL']}" not in profile["WORKER_PROCESS_COMMAND"]
    ):
        reasons.add("runtime_profile_process_mismatch")
    reasons.update(_counter_failure_reasons(run_dir / "commands.log"))
    return BaselineValidation(not reasons, tuple(sorted(reasons)), tuple(sorted(warnings)))
