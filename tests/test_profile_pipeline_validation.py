import json
import hashlib
from pathlib import Path

import pytest

from scripts.profile_pipeline_validation import validate_profile_artifacts


RUN_ID = "profile_validation_fixture"
PROFILE = {
    "LOCAL_AI_BACKEND": "http",
    "LOCAL_AI_HTTP_API": "ollama",
    "LOCAL_AI_HTTP_PROFILE": "conservative",
    "LOCAL_AI_HTTP_MODEL": "gemma-3-270m-custom",
    "LOCAL_AI_HTTP_TIMEOUT_SECONDS": "300",
    "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS": "300",
    "LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS": "180",
    "LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS": "180",
    "LOCAL_AI_HTTP_MAX_RETRIES": "0",
    "WORKER_CONCURRENCY": "3",
    "WORKER_POOL": "prefork",
    "OLLAMA_NUM_PARALLEL": "1",
    "SEMANTIC_BACKEND": "pgvector",
    "SEMANTIC_CONTENT_MAX_CHARS": "4000",
    "SEMANTIC_ENABLED": "true",
    "SEMANTIC_MODEL_NAME": "all-MiniLM-L6-v2",
    "SEMANTIC_WORKER_PROCESS_COMMAND": "celery -A pipeline.semantic_tasks",
    "WORKER_PROCESS_COMMAND": "celery -A pipeline.tasks --concurrency=3 --pool=prefork",
}
ELIGIBILITY = (
    ("extract_parallel", "catalog", [1, 2]),
    ("segment_agenda", "catalog", [1]),
    ("summarize", "catalog", [1, 2]),
    ("entity_backfill", "catalog", [1, 2]),
    ("table_extraction", "catalog", [1, 2]),
    ("org_backfill", "place", []),
    ("org_backfill", "event", [10]),
    ("topic_modeling", "catalog", [1, 2]),
)
SPANS = (
    "extract_parallel",
    "segment_agenda",
    "summarize",
    "pipeline_total",
    "entity_backfill",
    "table_extraction",
    "org_backfill",
    "topic_modeling",
    "batch_enrichment_total",
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_artifacts(run_dir: Path) -> None:
    run_dir.mkdir(exist_ok=True)
    manifest_bytes = b"1\n2\n"
    (run_dir / "catalog_manifest.txt").write_bytes(manifest_bytes)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": RUN_ID,
            "mode": "baseline",
            "baseline_valid": False,
            "include_batch": True,
            "profile": PROFILE,
            "source_manifest": "profiling/manifests/baseline_representative_v2.txt",
            "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "git_commit": "abc123",
            "tracked_tree_clean": True,
        },
    )
    _write_json(
        run_dir / "result.json",
        {
            "run_id": RUN_ID,
            "status": "completed",
            "error": None,
            "include_batch": True,
            "segments": [
                {"name": "pipeline", "status": "completed"},
                {"name": "pipeline-batch", "status": "completed"},
            ],
        },
    )
    _write_json(
        run_dir / "day_summary.json",
        {
            "run_id": RUN_ID,
            "provider_metrics_present": True,
            "provider_requests_delta_run": 2.0,
            "provider_timeouts_delta_run": 0.0,
            "provider_retries_delta_run": 0.0,
            "search_p95_ms": 12.5,
        },
    )
    rows: list[dict[str, object]] = []
    for phase, subject, eligible_ids in ELIGIBILITY:
        rows.extend(
            [
                {
                    "run_id": RUN_ID,
                    "event_type": "phase_eligibility",
                    "phase": phase,
                    "boundary": "before",
                    "subject": subject,
                    "eligible_ids": eligible_ids,
                    "eligible_count": len(eligible_ids),
                },
                {
                    "run_id": RUN_ID,
                    "event_type": "phase_eligibility",
                    "phase": phase,
                    "boundary": "after",
                    "subject": subject,
                    "eligible_ids": [],
                    "eligible_count": 0,
                },
            ]
        )
    rows.extend(
        {
            "run_id": RUN_ID,
            "event_type": "span",
            "phase": phase,
            "outcome": "success",
            "duration_s": 0.1,
        }
        for phase in SPANS
    )
    (run_dir / "spans.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )
    (run_dir / "commands.log").write_text(
        "\n".join(
            [
                "agenda_segmentation_backfill selected=1 complete=1 empty=0 failed=0 other=0",
                "summary_hydration_backfill selected=2 complete=2 error=0 other=0 not_generated_yet=0 reindex_failed=0 embed_enqueued=0 embed_dispatch_failed=0",
                "entity_backfill selected=2 complete=2 failed=0 other=0",
                "topic_hydration_backfill selected=2 complete=2 error=0 other=0 reindex_failed=0",
                "targeted_reindex_summary requested=2 reindexed=2 failed=0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_complete_terminal_evidence_is_valid(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert validation.valid
    assert validation.reasons == ()
    assert validation.warnings == ()


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("result_failed", "result_not_completed"),
        ("missing_phase_after", "phase_eligibility_incomplete:segment_agenda:catalog"),
        ("gating_remainder", "phase_remainder_nonzero:summarize:catalog"),
        ("failed_span", "phase_span_failed:summarize"),
        ("missing_provider_delta", "provider_deltas_incomplete"),
        ("missing_profile", "runtime_profile_incomplete"),
        ("missing_search", "search_measurement_missing"),
        ("reindex_failure", "side_effect_failure:reindex_failed"),
        ("manifest_copy_mismatch", "source_manifest_copy_mismatch"),
    ],
)
def test_incomplete_or_failed_evidence_is_invalid(
    tmp_path: Path,
    mutation: str,
    expected_reason: str,
) -> None:
    _write_valid_artifacts(tmp_path)
    if mutation == "result_failed":
        result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
        result["status"] = "failed"
        _write_json(tmp_path / "result.json", result)
    elif mutation in {"missing_phase_after", "gating_remainder", "failed_span"}:
        rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text().splitlines()]
        if mutation == "missing_phase_after":
            rows = [
                row
                for row in rows
                if not (
                    row.get("event_type") == "phase_eligibility"
                    and row.get("phase") == "segment_agenda"
                    and row.get("boundary") == "after"
                )
            ]
        elif mutation == "gating_remainder":
            row = next(
                row
                for row in rows
                if row.get("phase") == "summarize" and row.get("boundary") == "after"
            )
            row.update({"eligible_ids": [2], "eligible_count": 1})
        else:
            row = next(
                row
                for row in rows
                if row.get("event_type") == "span" and row.get("phase") == "summarize"
            )
            row["outcome"] = "failure"
        (tmp_path / "spans.jsonl").write_text(
            "".join(f"{json.dumps(row)}\n" for row in rows), encoding="utf-8"
        )
    elif mutation in {"missing_provider_delta", "missing_search"}:
        day = json.loads((tmp_path / "day_summary.json").read_text(encoding="utf-8"))
        day.pop("provider_requests_delta_run" if mutation == "missing_provider_delta" else "search_p95_ms")
        _write_json(tmp_path / "day_summary.json", day)
    elif mutation == "missing_profile":
        manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
        manifest["profile"].pop("LOCAL_AI_HTTP_MODEL")
        _write_json(tmp_path / "run_manifest.json", manifest)
    elif mutation == "manifest_copy_mismatch":
        (tmp_path / "catalog_manifest.txt").write_text("3\n", encoding="utf-8")
    else:
        with (tmp_path / "commands.log").open("a", encoding="utf-8") as command_log:
            command_log.write("summary_hydration_backfill selected=1 reindex_failed=1\n")

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert not validation.valid
    assert expected_reason in validation.reasons


def test_extraction_remainder_is_warning_only(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)
    rows = [json.loads(line) for line in (tmp_path / "spans.jsonl").read_text().splitlines()]
    extraction_after = next(
        row
        for row in rows
        if row.get("phase") == "extract_parallel" and row.get("boundary") == "after"
    )
    extraction_after.update({"eligible_ids": [2], "eligible_count": 1})
    (tmp_path / "spans.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows), encoding="utf-8"
    )

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert validation.valid
    assert validation.warnings == ("extraction_remainder_nonzero",)


def test_published_task_without_terminal_success_is_invalid(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)
    with (tmp_path / "spans.jsonl").open("a", encoding="utf-8") as spans:
        for boundary in ("before", "after"):
            spans.write(
                json.dumps(
                    {
                        "run_id": RUN_ID,
                        "event_type": "task_dispatch",
                        "boundary": boundary,
                        "task_id": "task-1",
                        "retry_ordinal": 0,
                    }
                )
                + "\n"
            )

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert not validation.valid
    assert "task_start_missing" in validation.reasons


def test_started_task_without_completed_dispatch_is_invalid(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)
    with (tmp_path / "spans.jsonl").open("a", encoding="utf-8") as spans:
        for event_type in ("task_start", "task_span"):
            spans.write(
                json.dumps(
                    {
                        "run_id": RUN_ID,
                        "event_type": event_type,
                        "task_id": "task-1",
                        "execution_id": "attempt-1",
                        "retry_ordinal": 0,
                        "outcome": "success" if event_type == "task_span" else None,
                    }
                )
                + "\n"
            )

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert not validation.valid
    assert "missing_task_dispatch" in validation.reasons


def test_embed_enqueue_count_requires_matching_dispatch_evidence(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)
    command_log = tmp_path / "commands.log"
    command_log.write_text(
        command_log.read_text(encoding="utf-8").replace("embed_enqueued=0", "embed_enqueued=1"),
        encoding="utf-8",
    )

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert not validation.valid
    assert "task_dispatch_count_mismatch" in validation.reasons


def test_unrelated_task_dispatch_does_not_satisfy_embed_enqueue_count(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)
    command_log = tmp_path / "commands.log"
    command_log.write_text(
        command_log.read_text(encoding="utf-8").replace("embed_enqueued=0", "embed_enqueued=1"),
        encoding="utf-8",
    )
    with (tmp_path / "spans.jsonl").open("a", encoding="utf-8") as spans:
        for boundary in ("before", "after"):
            spans.write(
                json.dumps(
                    {
                        "run_id": RUN_ID,
                        "event_type": "task_dispatch",
                        "boundary": boundary,
                        "task_id": "unrelated-task",
                        "task_name": "pipeline.generate_summary_task",
                        "retry_ordinal": 0,
                    }
                )
                + "\n"
            )
        for event_type in ("task_start", "task_span"):
            spans.write(
                json.dumps(
                    {
                        "run_id": RUN_ID,
                        "event_type": event_type,
                        "task_id": "unrelated-task",
                        "execution_id": "unrelated-attempt",
                        "retry_ordinal": 0,
                        "outcome": "success" if event_type == "task_span" else None,
                    }
                )
                + "\n"
            )

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert not validation.valid
    assert "task_dispatch_count_mismatch" in validation.reasons


def test_dispatched_retry_without_its_own_terminal_evidence_is_invalid(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)
    with (tmp_path / "spans.jsonl").open("a", encoding="utf-8") as spans:
        for retry_ordinal in (0, 1):
            for boundary in ("before", "after"):
                spans.write(
                    json.dumps(
                        {
                            "run_id": RUN_ID,
                            "event_type": "task_dispatch",
                            "boundary": boundary,
                            "task_id": "retry-task",
                            "task_name": "pipeline.generate_summary_task",
                            "retry_ordinal": retry_ordinal,
                        }
                    )
                    + "\n"
                )
        for event_type in ("task_start", "task_span"):
            spans.write(
                json.dumps(
                    {
                        "run_id": RUN_ID,
                        "event_type": event_type,
                        "task_id": "retry-task",
                        "execution_id": "attempt-0",
                        "retry_ordinal": 0,
                        "outcome": "success" if event_type == "task_span" else None,
                    }
                )
                + "\n"
            )

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert not validation.valid
    assert "task_start_missing" in validation.reasons
    assert "task_terminal_missing" in validation.reasons


def test_successful_retry_supersedes_failed_attempt(tmp_path: Path) -> None:
    _write_valid_artifacts(tmp_path)
    with (tmp_path / "spans.jsonl").open("a", encoding="utf-8") as spans:
        for retry_ordinal, outcome in ((0, "failure"), (1, "success")):
            for boundary in ("before", "after"):
                spans.write(
                    json.dumps(
                        {
                            "run_id": RUN_ID,
                            "event_type": "task_dispatch",
                            "boundary": boundary,
                            "task_id": "retry-task",
                            "retry_ordinal": retry_ordinal,
                        }
                    )
                    + "\n"
                )
            for event_type in ("task_start", "task_span"):
                spans.write(
                    json.dumps(
                        {
                            "run_id": RUN_ID,
                            "event_type": event_type,
                            "task_id": "retry-task",
                            "execution_id": f"attempt-{retry_ordinal}",
                            "retry_ordinal": retry_ordinal,
                            "outcome": outcome if event_type == "task_span" else None,
                        }
                    )
                    + "\n"
                )

    validation = validate_profile_artifacts(tmp_path, expected_run_id=RUN_ID, include_batch=True)

    assert validation.valid
