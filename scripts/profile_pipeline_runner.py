from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Callable

from scripts.profile_pipeline_commands import build_profile_commands, profile_env
from scripts.profile_pipeline_results import write_result_manifest, write_run_manifest


BASELINE_QUARANTINE_MESSAGE = (
    "promotion-grade baseline execution is quarantined pending evidence-integrity activation; "
    "use --diagnostic"
)
RETIRED_REPLAY_MESSAGE = "synthetic replay packages are retired; use a text-only fresh-work diagnostic manifest"


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


def require_non_promotional_baseline(args: Any) -> None:
    if args.mode == "baseline" and not args.diagnostic:
        raise SystemExit(BASELINE_QUARANTINE_MESSAGE)


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


def run_profile(args: Any, deps: ProfilePipelineDeps) -> int:
    require_non_promotional_baseline(args)
    if args.mode == "baseline" and not args.manifest:
        raise SystemExit("--manifest is required for baseline mode")
    if args.diagnostic and args.mode != "baseline":
        raise SystemExit("--diagnostic is only supported for baseline mode")
    baseline_valid = args.mode == "baseline" and not args.diagnostic
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
        baseline_valid=baseline_valid,
        city=args.city,
        include_batch=not args.skip_batch,
        catalog_ids=catalog_ids,
        provider_counters_before_run=provider_counters_before_run,
    )
    artifact_dir_rel = deps.path_for_profile_env(run_dir)
    env = profile_env(
        run_id=run_id,
        mode=args.mode,
        artifact_dir=artifact_dir_rel,
        baseline_valid=baseline_valid,
        manifest_path=manifest_rel,
    )
    commands = build_profile_commands(
        args=args,
        core_service=deps.core_service,
        batch_service=deps.batch_service,
        run_id=run_id,
        artifact_dir_rel=artifact_dir_rel,
        manifest_rel=manifest_rel,
        baseline_valid=baseline_valid,
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
            status="commands_completed",
            baseline_valid=baseline_valid,
            started_at=started_at,
            started=started,
            include_batch=not args.skip_batch,
            command_segments=command_segments,
            command_log=command_log,
            error_message=None,
        )
        _run_post_processors(args, deps, run_id, output_root)
        status = "completed"
        return 0
    except (subprocess.CalledProcessError, OSError) as exc:
        error_message = f"{exc.__class__.__name__}: {exc}"
        if isinstance(exc, subprocess.CalledProcessError):
            attempted = "pipeline-batch" if "run_batch_enrichment.py" in (exc.cmd or []) else "pipeline"
            if not command_segments or command_segments[-1]["name"] != attempted:
                command_segments.append(
                    {"name": attempted, "command": exc.cmd, "status": "failed", "elapsed_seconds": 0.0}
                )
        raise
    finally:
        _write_result(
            deps,
            run_dir,
            run_id,
            status=status,
            baseline_valid=baseline_valid,
            started_at=started_at,
            started=started,
            include_batch=not args.skip_batch,
            command_segments=command_segments,
            command_log=command_log,
            error_message=error_message,
        )
        print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": status}, indent=2))


def _write_result(
    deps: ProfilePipelineDeps,
    run_dir: Path,
    run_id: str,
    *,
    status: str,
    baseline_valid: bool,
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
        baseline_valid=baseline_valid,
        started_at=started_at,
        started=started,
        include_batch=include_batch,
        command_segments=command_segments,
        command_log=command_log,
        error_message=error_message,
    )
