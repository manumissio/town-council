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


def _profile_env(*, run_id: str, mode: str, artifact_dir: str, baseline_valid: bool, manifest_path: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TC_PROFILE_RUN_ID"] = run_id
    env["TC_PROFILE_MODE"] = mode
    env["TC_PROFILE_ARTIFACT_DIR"] = artifact_dir
    env["TC_PROFILE_BASELINE_VALID"] = "1" if baseline_valid else "0"
    env["TC_PROFILE_CATALOG_MANIFEST"] = manifest_path
    env["TC_PROFILE_WORKLOAD_ONLY"] = "1"
    return env


def _profile_command(*, service: str, script_name: str, run_id: str, mode: str, artifact_dir_rel: str, manifest_rel: str) -> list[str]:
    return [
        "docker",
        "compose",
        "exec",
        "-T",
        "-e",
        f"TC_PROFILE_RUN_ID={run_id}",
        "-e",
        f"TC_PROFILE_MODE={mode}",
        "-e",
        f"TC_PROFILE_ARTIFACT_DIR={artifact_dir_rel}",
        "-e",
        f"TC_PROFILE_BASELINE_VALID={'1' if mode == 'baseline' else '0'}",
        "-e",
        f"TC_PROFILE_CATALOG_MANIFEST={manifest_rel}",
        "-e",
        "TC_PROFILE_WORKLOAD_ONLY=1",
        "-w",
        "/app/pipeline",
        service,
        "python",
        script_name,
    ]


def _build_commands(args: Any, deps: ProfilePipelineDeps, run_id: str, artifact_dir_rel: str, manifest_rel: str) -> list[list[str]]:
    commands = [
        _profile_command(
            service=deps.core_service,
            script_name="run_pipeline.py",
            run_id=run_id,
            mode=args.mode,
            artifact_dir_rel=artifact_dir_rel,
            manifest_rel=manifest_rel,
        )
    ]
    if not args.skip_batch:
        commands.append(
            _profile_command(
                service=deps.batch_service,
                script_name="run_batch_enrichment.py",
                run_id=run_id,
                mode=args.mode,
                artifact_dir_rel=artifact_dir_rel,
                manifest_rel=manifest_rel,
            )
        )
    return commands


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


def _manifest_package_summary(manifest_package: dict) -> dict[str, Any]:
    return {
        "schema_version": int(manifest_package.get("schema_version") or 0),
        "manifest_name": manifest_package.get("manifest_name"),
        "phase_selected_counts": {key: len(value) for key, value in (manifest_package.get("strata") or {}).items()},
        "expected_phase_coverage": dict(manifest_package.get("expected_phase_coverage") or {}),
    }


def _write_run_manifest(
    *,
    deps: ProfilePipelineDeps,
    run_dir: Path,
    run_id: str,
    args: Any,
    catalog_ids: list[int],
    provider_counters_before_run: dict[str, float] | None,
    manifest_package: dict | None,
) -> dict[str, Any]:
    run_manifest: dict[str, Any] = {
        "run_id": run_id,
        "mode": args.mode,
        "started_at": deps.utc_now_iso(),
        "baseline_valid": args.mode == "baseline",
        "catalog_ids": catalog_ids,
        "catalog_count": len(catalog_ids),
        "city": args.city,
        "include_batch": not args.skip_batch,
        "workload_only": True,
        "profile": {
            key: os.getenv(key)
            for key in (
                "LOCAL_AI_BACKEND",
                "LOCAL_AI_HTTP_PROFILE",
                "LOCAL_AI_HTTP_MODEL",
                "WORKER_CONCURRENCY",
                "WORKER_POOL",
                "OLLAMA_NUM_PARALLEL",
            )
            if os.getenv(key) is not None
        },
        "provider_counters_before_run": provider_counters_before_run,
    }
    if manifest_package is not None:
        run_manifest["manifest_package"] = _manifest_package_summary(manifest_package)
    deps.write_json(run_dir / "run_manifest.json", run_manifest)
    return run_manifest


def _run_post_processors(args: Any, deps: ProfilePipelineDeps, run_id: str, output_root: Path) -> None:
    for command in (
        [deps.sys_executable, str(deps.repo_root / "scripts" / "collect_soak_metrics.py"), "--run-id", run_id, "--output-dir", str(output_root), "--api-url", args.api_url],
        [deps.sys_executable, str(deps.repo_root / "scripts" / "analyze_pipeline_profile.py"), "--run-id", run_id, "--output-dir", str(output_root)],
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

    run_manifest = _write_run_manifest(
        deps=deps,
        run_dir=run_dir,
        run_id=run_id,
        args=args,
        catalog_ids=catalog_ids,
        provider_counters_before_run=provider_counters_before_run,
        manifest_package=manifest_package,
    )
    artifact_dir_rel = deps.path_for_profile_env(run_dir)
    env = _profile_env(run_id=run_id, mode=args.mode, artifact_dir=artifact_dir_rel, baseline_valid=args.mode == "baseline", manifest_path=manifest_rel)
    commands = _build_commands(args, deps, run_id, artifact_dir_rel, manifest_rel)
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
            command_segments.append({"name": segment_name, "command": command, "status": "completed", "elapsed_seconds": round(time.perf_counter() - segment_started, 3)})
        _write_result(deps, run_dir, run_id, status="commands_completed", started_at=started_at, started=started, include_batch=not args.skip_batch, command_segments=command_segments, command_log=command_log, error_message=None)
        _run_post_processors(args, deps, run_id, output_root)
        status = "completed"
        return 0
    except (subprocess.CalledProcessError, OSError) as exc:
        error_message = f"{exc.__class__.__name__}: {exc}"
        if isinstance(exc, subprocess.CalledProcessError):
            attempted = "pipeline-batch" if "run_batch_enrichment.py" in (exc.cmd or []) else "pipeline"
            if not command_segments or command_segments[-1]["name"] != attempted:
                command_segments.append({"name": attempted, "command": exc.cmd, "status": "failed", "elapsed_seconds": 0.0})
        raise
    finally:
        _write_result(deps, run_dir, run_id, status=status, started_at=started_at, started=started, include_batch=not args.skip_batch, command_segments=command_segments, command_log=command_log, error_message=error_message)
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
    from scripts.operator_profile_artifacts import build_result_payload

    deps.write_json(
        run_dir / "result.json",
        build_result_payload(
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=deps.utc_now_iso(),
            elapsed_seconds=time.perf_counter() - started,
            include_batch=include_batch,
            segments=command_segments,
            error_message=error_message,
            quality=deps.segment_status_from_log(command_log),
        ),
    )
