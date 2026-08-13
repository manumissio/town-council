from __future__ import annotations

import os
from typing import Any


PROFILE_EXECUTION_ISOLATION_ARGS = (
    "-e",
    "STARTUP_PURGE_DERIVED=false",
    "-e",
    "PIPELINE_ONBOARDING_CITY=",
    "-e",
    "PIPELINE_ONBOARDING_STARTED_AT_UTC=",
    "-e",
    "PIPELINE_RUNTIME_PROFILE=",
)


def profile_env(*, run_id: str, mode: str, artifact_dir: str, manifest_path: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TC_PROFILE_RUN_ID"] = run_id
    env["TC_PROFILE_MODE"] = mode
    env["TC_PROFILE_ARTIFACT_DIR"] = artifact_dir
    env["TC_PROFILE_CATALOG_MANIFEST"] = manifest_path
    env["TC_PROFILE_WORKLOAD_ONLY"] = "1"
    return env


def profile_command(
    *,
    service: str,
    script_name: str,
    run_id: str,
    mode: str,
    artifact_dir_rel: str,
    manifest_rel: str,
) -> list[str]:
    return [
        "docker",
        "compose",
        "exec",
        "-T",
        *PROFILE_EXECUTION_ISOLATION_ARGS,
        "-e",
        f"TC_PROFILE_RUN_ID={run_id}",
        "-e",
        f"TC_PROFILE_MODE={mode}",
        "-e",
        f"TC_PROFILE_ARTIFACT_DIR={artifact_dir_rel}",
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


def build_profile_commands(
    *,
    args: Any,
    core_service: str,
    batch_service: str,
    run_id: str,
    artifact_dir_rel: str,
    manifest_rel: str,
) -> list[list[str]]:
    commands = [
        profile_command(
            service=core_service,
            script_name="run_pipeline.py",
            run_id=run_id,
            mode=args.mode,
            artifact_dir_rel=artifact_dir_rel,
            manifest_rel=manifest_rel,
        )
    ]
    if not args.skip_batch:
        commands.append(
            profile_command(
                service=batch_service,
                script_name="run_batch_enrichment.py",
                run_id=run_id,
                mode=args.mode,
                artifact_dir_rel=artifact_dir_rel,
                manifest_rel=manifest_rel,
            )
        )
    return commands
