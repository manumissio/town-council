from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from pipeline.profile_manifest import load_manifest_package, sidecar_path_for_manifest, validate_manifest_package
from scripts.profile_pipeline_commands import build_profile_commands, profile_env
from scripts.profile_pipeline_results import write_result_manifest, write_run_manifest


@dataclass(frozen=True)
class ProfilePipelineDeps:
    repo_root: Path
    core_service: str
    batch_service: str
    load_manifest_catalog_ids: Callable[[Path], list[int]]
    path_for_profile_env: Callable[[Path], str]
    provider_counters_before_run: Callable[[], dict[str, float] | None]
    prepare_manifest_package_via_docker: Callable[[str], dict]
    run_backfill_catalog_hashes_via_docker: Callable[..., None]
    run_command: Callable[..., None]
    run_db_migrate_via_docker: Callable[..., None]
    select_triage_catalog_ids_via_docker: Callable[..., dict]
    segment_status_from_log: Callable[[Path], dict]
    subprocess_module: Any
    sys_executable: str
    utc_now_iso: Callable[[], str]
    write_catalog_manifest: Callable[[Path, list[int]], None]
    write_json: Callable[[Path, dict], None]


def _catalog_ids_for_args(args: Any, deps: ProfilePipelineDeps) -> tuple[list[int], dict | None, Path | None]:
    manifest_path = Path(args.manifest) if args.manifest else None
    if args.mode != "baseline":
        selection = deps.select_triage_catalog_ids_via_docker(limit=max(1, int(args.limit)), city=args.city)
        return [int(cid) for cid in selection.get("catalog_ids") or []], None, manifest_path
    assert manifest_path is not None
    catalog_ids = deps.load_manifest_catalog_ids(manifest_path)
    manifest_package = load_manifest_package(manifest_path)
    if manifest_package is not None:
        validate_manifest_package(catalog_ids, manifest_package)
    return catalog_ids, manifest_package, manifest_path


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
    if args.mode == "baseline" and not args.manifest:
        raise SystemExit("--manifest is required for baseline mode")
    run_id = args.run_id or f"pipeline_profile_{args.mode}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output_root = Path(args.output_dir)
    if not output_root.is_absolute():
        output_root = deps.repo_root / output_root
    run_dir = output_root / run_id
    if run_dir.exists():
        raise SystemExit(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    catalog_ids, manifest_package, _manifest_path = _catalog_ids_for_args(args, deps)
    if not catalog_ids:
        raise SystemExit("no catalog ids selected for profiling")

    manifest_copy = run_dir / "catalog_manifest.txt"
    deps.write_catalog_manifest(manifest_copy, catalog_ids)
    if manifest_package is not None:
        deps.write_json(sidecar_path_for_manifest(manifest_copy), manifest_package)
    provider_counters_before_run = deps.provider_counters_before_run()
    manifest_rel = deps.path_for_profile_env(manifest_copy)
    command_log = run_dir / "commands.log"
    if manifest_package is not None:
        deps.run_db_migrate_via_docker(log_path=command_log)
        deps.run_backfill_catalog_hashes_via_docker(log_path=command_log)
    if args.dry_run_prepare:
        if args.mode != "baseline":
            raise SystemExit("--dry-run-prepare is only supported for baseline mode")
        if manifest_package is None:
            raise SystemExit("--dry-run-prepare requires a manifest package sidecar (.json)")
        prepare_summary = deps.prepare_manifest_package_via_docker(manifest_rel, dry_run=True)
        print(json.dumps(prepare_summary, indent=2, sort_keys=True))
        return 0

    run_manifest = write_run_manifest(
        write_json=deps.write_json,
        utc_now_iso=deps.utc_now_iso,
        run_dir=run_dir,
        run_id=run_id,
        mode=args.mode,
        city=args.city,
        include_batch=not args.skip_batch,
        catalog_ids=catalog_ids,
        provider_counters_before_run=provider_counters_before_run,
        manifest_package=manifest_package,
    )
    artifact_dir_rel = deps.path_for_profile_env(run_dir)
    env = profile_env(
        run_id=run_id,
        mode=args.mode,
        artifact_dir=artifact_dir_rel,
        baseline_valid=args.mode == "baseline",
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
        if manifest_package is not None:
            run_manifest["preconditioning"] = deps.prepare_manifest_package_via_docker(manifest_rel, dry_run=False)
            deps.write_json(run_dir / "run_manifest.json", run_manifest)
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
