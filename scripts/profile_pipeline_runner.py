from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Callable

from scripts.profile_pipeline_commands import build_profile_commands, profile_env
from scripts.profile_pipeline_results import write_result_manifest, write_run_manifest
from scripts.profile_pipeline_runtime import capture_runtime_profile
from scripts.profile_pipeline_runtime import git_commit
from scripts.profile_pipeline_runtime import tracked_manifest_bytes
from scripts.profile_pipeline_runtime import tracked_tree_clean
from scripts.profile_pipeline_validation import BaselineValidation
from scripts.profile_pipeline_validation import load_profile_events
from scripts.profile_pipeline_validation import task_evidence_reasons
from scripts.profile_pipeline_validation import validate_profile_artifacts


RETIRED_REPLAY_MESSAGE = "synthetic replay packages are retired; use a text-only fresh-work diagnostic manifest"
TASK_SETTLE_TIMEOUT_SECONDS = 900.0
TASK_QUIET_SECONDS = 1.0
TASK_POLL_SECONDS = 0.2


@dataclass(frozen=True)
class ProfilePipelineDeps:
    repo_root: Path
    core_service: str
    batch_service: str
    load_manifest_catalog_ids: Callable[[Path], list[int]]
    path_for_profile_env: Callable[[Path], str]
    provider_counters_before_run: Callable[[], dict[str, float] | None]
    run_command: Callable[..., None]
    select_triage_catalog_ids_via_docker: Callable[..., dict]
    segment_status_from_log: Callable[[Path], dict]
    subprocess_module: Any
    sys_executable: str
    utc_now_iso: Callable[[], str]
    write_catalog_manifest: Callable[[Path, list[int]], None]
    write_json: Callable[[Path, dict], None]


def _catalog_ids_for_args(args: Any, deps: ProfilePipelineDeps) -> list[int]:
    manifest_path = Path(args.manifest) if args.manifest else None
    if args.mode != "baseline":
        selection = deps.select_triage_catalog_ids_via_docker(limit=max(1, int(args.limit)), city=args.city)
        return [int(cid) for cid in selection.get("catalog_ids") or []]
    assert manifest_path is not None
    if manifest_path.with_suffix(".json").exists():
        raise SystemExit(RETIRED_REPLAY_MESSAGE)
    catalog_ids = deps.load_manifest_catalog_ids(manifest_path)
    return catalog_ids


def _run_post_processors(args: Any, deps: ProfilePipelineDeps, run_id: str, output_root: Path) -> None:
    for command in (
        [
            deps.sys_executable,
            str(deps.repo_root / "scripts" / "collect_soak_metrics.py"),
            "--run-id",
            run_id,
            "--output-dir",
            str(output_root),
            "--api-url",
            args.api_url,
        ],
        [
            deps.sys_executable,
            str(deps.repo_root / "scripts" / "analyze_pipeline_profile.py"),
            "--run-id",
            run_id,
            "--output-dir",
            str(output_root),
        ],
    ):
        deps.subprocess_module.run(command, cwd=str(deps.repo_root), check=True, env=os.environ.copy())
    if args.compare_to:
        deps.subprocess_module.run(
            [
                deps.sys_executable,
                str(deps.repo_root / "scripts" / "analyze_pipeline_profile.py"),
                "--run-id",
                run_id,
                "--output-dir",
                str(output_root),
                "--compare-to",
                args.compare_to,
            ],
            cwd=str(deps.repo_root),
            check=True,
            env=os.environ.copy(),
        )


def _wait_for_terminal_tasks(run_dir: Path) -> None:
    deadline = time.monotonic() + TASK_SETTLE_TIMEOUT_SECONDS
    quiet_started: float | None = None
    previous_size = -1
    terminal = False
    events_path = run_dir / "spans.jsonl"
    while time.monotonic() < deadline:
        current_size = events_path.stat().st_size if events_path.exists() else 0
        if current_size != previous_size:
            profile_events, error = load_profile_events(events_path)
            pending_reasons = set(task_evidence_reasons(profile_events, require_terminal_dispatches=True))
            pending_reasons.discard("task_terminal_failed")
            terminal = error is None and not pending_reasons
            quiet_started = None
        elif terminal:
            quiet_started = quiet_started or time.monotonic()
            if time.monotonic() - quiet_started >= TASK_QUIET_SECONDS:
                return
        else:
            quiet_started = None
        previous_size = current_size
        time.sleep(TASK_POLL_SECONDS)
    raise RuntimeError("profile task evidence did not reach terminal closure")


def _finalize_run_manifest(
    deps: ProfilePipelineDeps,
    run_dir: Path,
    validation: BaselineValidation,
    *,
    diagnostic: bool,
) -> None:
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation_reasons = list(validation.reasons)
    if diagnostic:
        validation_reasons.insert(0, "diagnostic_run")
    manifest.update(
        {
            "baseline_valid": validation.valid and not diagnostic,
            "baseline_validation_reasons": validation_reasons,
            "baseline_validation_warnings": list(validation.warnings),
            "finished_at": deps.utc_now_iso(),
        }
    )
    deps.write_json(manifest_path, manifest)


def _runtime_profile_unchanged(repo_root: Path, expected_profile: dict[str, str]) -> bool:
    return capture_runtime_profile(repo_root) == expected_profile


def _record_invalid_manifest(
    deps: ProfilePipelineDeps,
    run_dir: Path,
    error_message: str,
) -> None:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as manifest_error:
        print(f"unable to record invalid profile manifest: {manifest_error}", file=sys.stderr)
        return
    validation_reasons = [
        str(reason)
        for reason in manifest.get("baseline_validation_reasons", [])
        if str(reason).strip() and reason != "run_incomplete"
    ]
    validation_reasons.extend(["run_failed", error_message])
    manifest.update(
        {
            "baseline_valid": False,
            "baseline_validation_reasons": list(dict.fromkeys(validation_reasons)),
            "finished_at": deps.utc_now_iso(),
        }
    )
    deps.write_json(manifest_path, manifest)


def run_profile(args: Any, deps: ProfilePipelineDeps) -> int:
    if args.mode == "baseline" and not args.manifest:
        raise SystemExit("--manifest is required for baseline mode")
    if args.diagnostic and args.mode != "baseline":
        raise SystemExit("--diagnostic is only supported for baseline mode")
    if args.mode == "baseline" and not args.diagnostic and args.skip_batch:
        raise SystemExit("baseline profiling requires batch enrichment")
    if args.mode == "baseline" and not args.diagnostic and args.compare_to:
        raise SystemExit("run expected-baseline comparison after capture finalization")
    run_id = args.run_id or f"pipeline_profile_{args.mode}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output_root = Path(args.output_dir)
    if not output_root.is_absolute():
        output_root = deps.repo_root / output_root
    run_dir = output_root / run_id
    if run_dir.exists():
        raise SystemExit(f"run directory already exists: {run_dir}")

    catalog_ids = _catalog_ids_for_args(args, deps)
    if not catalog_ids:
        raise SystemExit("no catalog ids selected for profiling")

    source_manifest = Path(args.manifest) if args.manifest else None
    source_manifest_name: str | None = None
    source_manifest_bytes = b""
    if source_manifest is not None and not args.diagnostic:
        source_manifest_name, source_manifest_bytes = tracked_manifest_bytes(source_manifest, deps.repo_root)
    elif source_manifest is not None:
        source_manifest_bytes = source_manifest.read_bytes()
    runtime_profile = capture_runtime_profile(deps.repo_root) if args.mode == "baseline" else {}
    initial_commit = git_commit(deps.repo_root)
    initial_tree_clean = tracked_tree_clean(deps.repo_root)
    if args.mode == "baseline" and not args.diagnostic and not initial_tree_clean:
        raise SystemExit("baseline profiling requires a clean tracked tree")

    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        manifest_copy = run_dir / "catalog_manifest.txt"
        deps.write_catalog_manifest(manifest_copy, catalog_ids)
        manifest_rel = deps.path_for_profile_env(manifest_copy)
        command_log = run_dir / "commands.log"
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError):
        shutil.rmtree(run_dir)
        raise
    provider_counters_before_run = deps.provider_counters_before_run()

    write_run_manifest(
        write_json=deps.write_json,
        utc_now_iso=deps.utc_now_iso,
        run_dir=run_dir,
        run_id=run_id,
        mode=args.mode,
        city=args.city,
        include_batch=not args.skip_batch,
        catalog_ids=catalog_ids,
        provider_counters_before_run=provider_counters_before_run,
        profile=runtime_profile,
        source_manifest=source_manifest_name or (str(source_manifest) if source_manifest else None),
        source_manifest_bytes=source_manifest_bytes,
        git_commit=initial_commit,
        tracked_tree_clean=initial_tree_clean,
    )
    artifact_dir_rel = deps.path_for_profile_env(run_dir)
    env = profile_env(
        run_id=run_id,
        mode=args.mode,
        artifact_dir=artifact_dir_rel,
        manifest_path=manifest_rel,
    )
    commands = build_profile_commands(
        args=args,
        core_service=deps.core_service,
        batch_service=deps.batch_service,
        run_id=run_id,
        artifact_dir_rel=artifact_dir_rel,
        manifest_rel=manifest_rel,
    )
    started = time.perf_counter()
    started_at = deps.utc_now_iso()
    status = "failed"
    error_message = None
    command_segments: list[dict] = []
    try:
        for command in commands:
            segment_started = time.perf_counter()
            segment_name = "pipeline-batch" if "run_batch_enrichment.py" in command else "pipeline"
            deps.run_command(command, env=env, cwd=deps.repo_root, log_path=command_log)
            command_segments.append(
                {
                    "name": segment_name,
                    "command": command,
                    "status": "completed",
                    "elapsed_seconds": round(time.perf_counter() - segment_started, 3),
                }
            )
        _write_result(
            deps,
            run_dir,
            run_id,
            status="completed",
            started_at=started_at,
            started=started,
            include_batch=not args.skip_batch,
            command_segments=command_segments,
            command_log=command_log,
            error_message=None,
        )
        _wait_for_terminal_tasks(run_dir)
        _run_post_processors(args, deps, run_id, output_root)
        if git_commit(deps.repo_root) != initial_commit or not tracked_tree_clean(deps.repo_root):
            raise RuntimeError("tracked source changed during profile run")
        if args.mode == "baseline" and not _runtime_profile_unchanged(deps.repo_root, runtime_profile):
            raise RuntimeError("runtime profile changed during profile run")
        if source_manifest is not None and not args.diagnostic:
            current_name, current_bytes = tracked_manifest_bytes(source_manifest, deps.repo_root)
            if current_name != source_manifest_name or current_bytes != source_manifest_bytes:
                raise RuntimeError("baseline manifest changed during profile run")
        if args.mode == "baseline":
            validation = validate_profile_artifacts(
                run_dir,
                expected_run_id=run_id,
                include_batch=not args.skip_batch,
            )
            _finalize_run_manifest(deps, run_dir, validation, diagnostic=args.diagnostic)
            if not args.diagnostic and not validation.valid:
                raise RuntimeError(f"baseline evidence invalid: {', '.join(validation.reasons)}")
        status = "completed"
        print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": status}, indent=2))
        return 0
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        error_message = f"{exc.__class__.__name__}: {exc}"
        if isinstance(exc, subprocess.CalledProcessError):
            attempted = "pipeline-batch" if "run_batch_enrichment.py" in (exc.cmd or []) else "pipeline"
            if not command_segments or command_segments[-1]["name"] != attempted:
                command_segments.append(
                    {"name": attempted, "command": exc.cmd, "status": "failed", "elapsed_seconds": 0.0}
                )
        _write_result(
            deps,
            run_dir,
            run_id,
            status=status,
            started_at=started_at,
            started=started,
            include_batch=not args.skip_batch,
            command_segments=command_segments,
            command_log=command_log,
            error_message=error_message,
        )
        _record_invalid_manifest(deps, run_dir, error_message)
        print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": status}, indent=2))
        raise


def _write_result(
    deps: ProfilePipelineDeps,
    run_dir: Path,
    run_id: str,
    *,
    status: str,
    started_at: str,
    started: float,
    include_batch: bool,
    command_segments: list[dict],
    command_log: Path,
    error_message: str | None,
) -> None:
    write_result_manifest(
        write_json=deps.write_json,
        segment_status_from_log=deps.segment_status_from_log,
        utc_now_iso=deps.utc_now_iso,
        run_dir=run_dir,
        run_id=run_id,
        status=status,
        started_at=started_at,
        started=started,
        include_batch=include_batch,
        command_segments=command_segments,
        command_log=command_log,
        error_message=error_message,
    )
