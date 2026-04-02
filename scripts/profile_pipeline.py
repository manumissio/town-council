#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from sqlalchemy.orm import sessionmaker

from pipeline.agenda_worker import select_catalog_ids_for_agenda_segmentation
from pipeline.maintenance_run_status import validate_run_id
from pipeline.models import Catalog, Document, Event, db_connect
from pipeline.profile_manifest import load_manifest_package, sidecar_path_for_manifest, validate_manifest_package
from pipeline.run_pipeline import select_catalog_ids_for_processing
from pipeline.tasks import select_catalog_ids_for_summary_hydration


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = "experiments/results/profiling"
DEFAULT_TRIAGE_LIMIT = 25
TRIAGE_SELECTOR_SERVICE = "worker"
CORE_PROFILE_SERVICE = "worker"
BATCH_PROFILE_SERVICE = "enrichment-worker"


def _safe_run_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_soak_metrics_module():
    path = REPO_ROOT / "scripts" / "collect_soak_metrics.py"
    spec = importlib.util.spec_from_file_location("collect_soak_metrics", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _json_dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _selected_city_catalog_ids(db, city: str) -> set[int]:
    aliases = {city.strip().lower().replace(" ", "_"), city.strip().lower().replace("_", " ")}
    rows = (
        db.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .filter(Event.source.in_(sorted(aliases)))
        .all()
    )
    return {int(row[0]) for row in rows}


def _select_triage_catalog_ids(limit: int, city: str | None) -> list[int]:
    Session = sessionmaker(bind=db_connect())
    db = Session()
    try:
        city_ids = _selected_city_catalog_ids(db, city) if city else None
        candidates: list[int] = []
        seen: set[int] = set()

        def add_all(ids: list[int]) -> None:
            for catalog_id in ids:
                cid = int(catalog_id)
                if city_ids is not None and cid not in city_ids:
                    continue
                if cid in seen:
                    continue
                seen.add(cid)
                candidates.append(cid)
                if len(candidates) >= limit:
                    return

        add_all(select_catalog_ids_for_processing(db))
        if len(candidates) < limit:
            add_all(select_catalog_ids_for_agenda_segmentation(db, limit=limit * 2))
        if len(candidates) < limit:
            add_all(select_catalog_ids_for_summary_hydration(db, limit=limit * 2, city=city))
        if len(candidates) < limit:
            fallback_query = (
                db.query(Catalog.id)
                .join(Document, Document.catalog_id == Catalog.id)
                .filter(Catalog.content.isnot(None), Catalog.content != "")
                .order_by(Catalog.id.desc())
            )
            for row in fallback_query.limit(limit * 4).all():
                add_all([int(row[0])])
                if len(candidates) >= limit:
                    break
        return candidates[:limit]
    finally:
        db.close()


def _load_manifest_catalog_ids(path: Path) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        cid = int(line)
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def _write_catalog_manifest(path: Path, catalog_ids: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{cid}\n" for cid in catalog_ids), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload), encoding="utf-8")


def _profile_env(*, run_id: str, mode: str, artifact_dir: str, baseline_valid: bool, manifest_path: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TC_PROFILE_RUN_ID"] = run_id
    env["TC_PROFILE_MODE"] = mode
    env["TC_PROFILE_ARTIFACT_DIR"] = artifact_dir
    env["TC_PROFILE_BASELINE_VALID"] = "1" if baseline_valid else "0"
    env["TC_PROFILE_CATALOG_MANIFEST"] = manifest_path
    env["TC_PROFILE_WORKLOAD_ONLY"] = "1"
    return env


def _path_for_profile_env(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        # Prefer repo-relative paths so compose-run containers can see the same
        # files, but keep the CLI testable with temporary directories.
        return str(path)


def _provider_counters_before_run() -> dict[str, float] | None:
    mod = _load_soak_metrics_module()
    raw, err = mod._fetch_worker_metrics_via_docker()
    if err or not raw.strip():
        return None
    rows = mod._parse_metrics(raw)
    return {
        "provider_requests_total": float(mod._sum_metric(rows, "tc_provider_requests_total")),
        "provider_timeouts_total": float(mod._sum_metric(rows, "tc_provider_timeouts_total")),
        "provider_retries_total": float(mod._sum_metric(rows, "tc_provider_retries_total")),
    }


def _run_command(command: list[str], *, env: dict[str, str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(command)}\n")
        handle.flush()
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command)


def _run_json_command(command: list[str], *, cwd: Path) -> dict:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    for raw_line in reversed(completed.stdout.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeError(f"expected JSON object in stdout for command: {' '.join(command)}")


def _prepare_manifest_package_via_docker(manifest_rel: str, *, dry_run: bool) -> dict:
    statement = (
        "import json; "
        "from pathlib import Path; "
        "from pipeline.profile_manifest import apply_preconditioning, load_manifest_package; "
        f"manifest_path=Path({manifest_rel!r}); "
        "package=load_manifest_package(manifest_path); "
        "assert package is not None, 'manifest package missing'; "
        f"print(json.dumps(apply_preconditioning(package, dry_run={str(bool(dry_run))}), sort_keys=True))"
    )
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-w",
        "/app",
        TRIAGE_SELECTOR_SERVICE,
        "python",
        "-c",
        statement,
    ]
    return _run_json_command(command, cwd=REPO_ROOT)


def _run_db_migrate_via_docker(*, log_path: Path) -> None:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-w",
        "/app/pipeline",
        TRIAGE_SELECTOR_SERVICE,
        "python",
        "db_migrate.py",
    ]
    _run_command(command, env=os.environ.copy(), cwd=REPO_ROOT, log_path=log_path)


def _select_triage_catalog_ids_via_docker(limit: int, city: str | None) -> dict:
    selector = (
        "import json; "
        "from scripts.profile_pipeline import _select_triage_catalog_ids; "
        f"ids=_select_triage_catalog_ids(limit={int(limit)}, city={city!r}); "
        "print(json.dumps({'catalog_ids': ids, 'catalog_count': len(ids)}))"
    )
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        TRIAGE_SELECTOR_SERVICE,
        "python",
        "-c",
        selector,
    ]
    return _run_json_command(command, cwd=REPO_ROOT)


def _build_result_payload(
    *,
    run_id: str,
    status: str,
    started_at: str,
    finished_at: str,
    elapsed_seconds: float,
    include_batch: bool,
    segments: list[dict],
    error_message: str | None,
    quality: dict,
) -> dict:
    core_elapsed = next((float(item["elapsed_seconds"]) for item in segments if item["name"] == "pipeline"), None)
    batch_elapsed = next((float(item["elapsed_seconds"]) for item in segments if item["name"] == "pipeline-batch"), None)
    combined_elapsed = sum(float(item["elapsed_seconds"]) for item in segments if item.get("status") == "completed")
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": round(float(elapsed_seconds), 3),
        "include_batch": include_batch,
        "segments": segments,
        "totals": {
            "core_elapsed_seconds": round(core_elapsed, 3) if core_elapsed is not None else None,
            "batch_elapsed_seconds": round(batch_elapsed, 3) if batch_elapsed is not None else None,
            "combined_elapsed_seconds": round(combined_elapsed, 3),
        },
        "profile": {
            "workload_only": True,
        },
        "quality": quality,
        "error": error_message,
    }


def _segment_status_from_log(command_log: Path) -> dict:
    if not command_log.exists():
        return {"notes": [], "flags": {}}
    lines = command_log.read_text(encoding="utf-8", errors="ignore").splitlines()
    notes: list[str] = []
    flags: dict[str, bool] = {}

    skip_lines = [line for line in lines if "Skipping file:" in line]
    failed_downloads = [line for line in lines if "Failed to download:" in line]
    if skip_lines and all("too large" in line for line in skip_lines) and len(failed_downloads) == len(skip_lines):
        notes.append("downloader_only_encountered_oversized_file_skips")
        flags["oversized_download_skips_only"] = True

    for idx, line in enumerate(lines):
        if "Agenda Segmentation Backfill" not in line:
            continue
        window = lines[idx:idx + 12]
        metrics: dict[str, int] = {}
        for entry in window:
            if ":" not in entry:
                continue
            key, value = entry.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"selected", "complete", "empty", "failed", "other"}:
                try:
                    metrics[key] = int(value)
                except ValueError:
                    pass
        if metrics.get("selected", 0) > 0 and metrics.get("failed") == metrics.get("selected") and metrics.get("complete", 0) == 0:
            notes.append("all_selected_docs_already_in_failed_segmentation_bucket")
            flags["all_failed_segmentation_bucket"] = True
            break

    return {"notes": notes, "flags": flags}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile the end-to-end Town Council pipeline.")
    parser.add_argument("--mode", choices=("triage", "baseline"), required=True)
    parser.add_argument("--run-id", type=_safe_run_id, default=None)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", help="Pinned catalog manifest for baseline runs.")
    parser.add_argument("--limit", type=int, default=DEFAULT_TRIAGE_LIMIT)
    parser.add_argument("--city", default=None)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--skip-batch", action="store_true")
    parser.add_argument("--dry-run-prepare", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "baseline" and not args.manifest:
        raise SystemExit("--manifest is required for baseline mode")

    run_id = args.run_id or f"pipeline_profile_{args.mode}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output_root = Path(args.output_dir)
    if not output_root.is_absolute():
        output_root = REPO_ROOT / output_root
    run_dir = output_root / run_id
    if run_dir.exists():
        raise SystemExit(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    manifest_package = None
    manifest_path = Path(args.manifest) if args.manifest else None
    if args.mode == "baseline":
        assert manifest_path is not None
        catalog_ids = _load_manifest_catalog_ids(manifest_path)
        manifest_package = load_manifest_package(manifest_path)
        if manifest_package is not None:
            validate_manifest_package(catalog_ids, manifest_package)
    else:
        selection = _select_triage_catalog_ids_via_docker(limit=max(1, int(args.limit)), city=args.city)
        catalog_ids = [int(cid) for cid in selection.get("catalog_ids") or []]
    if not catalog_ids:
        raise SystemExit("no catalog ids selected for profiling")

    manifest_copy = run_dir / "catalog_manifest.txt"
    _write_catalog_manifest(manifest_copy, catalog_ids)
    if manifest_package is not None:
        _write_json(sidecar_path_for_manifest(manifest_copy), manifest_package)
    provider_counters_before_run = _provider_counters_before_run()
    manifest_rel = _path_for_profile_env(manifest_copy)
    prepare_summary = None
    command_log = run_dir / "commands.log"
    if manifest_package is not None:
        _run_db_migrate_via_docker(log_path=command_log)
    if args.dry_run_prepare:
        if args.mode != "baseline":
            raise SystemExit("--dry-run-prepare is only supported for baseline mode")
        if manifest_package is None:
            raise SystemExit("--dry-run-prepare requires a manifest package sidecar (.json)")
        prepare_summary = _prepare_manifest_package_via_docker(manifest_rel, dry_run=True)
        print(json.dumps(prepare_summary, indent=2, sort_keys=True))
        return 0

    run_manifest = {
        "run_id": run_id,
        "mode": args.mode,
        "started_at": _utc_now_iso(),
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
        run_manifest["manifest_package"] = {
            "schema_version": int(manifest_package.get("schema_version") or 0),
            "manifest_name": manifest_package.get("manifest_name"),
            "phase_selected_counts": {
                key: len(value)
                for key, value in (manifest_package.get("strata") or {}).items()
            },
            "expected_phase_coverage": dict(manifest_package.get("expected_phase_coverage") or {}),
        }
    _write_json(run_dir / "run_manifest.json", run_manifest)

    artifact_dir_rel = _path_for_profile_env(run_dir)
    env = _profile_env(
        run_id=run_id,
        mode=args.mode,
        artifact_dir=artifact_dir_rel,
        baseline_valid=args.mode == "baseline",
        manifest_path=manifest_rel,
    )

    commands = [
        ["docker", "compose", "exec", "-T", "-e", f"TC_PROFILE_RUN_ID={run_id}", "-e", f"TC_PROFILE_MODE={args.mode}", "-e", f"TC_PROFILE_ARTIFACT_DIR={artifact_dir_rel}", "-e", f"TC_PROFILE_BASELINE_VALID={'1' if args.mode == 'baseline' else '0'}", "-e", f"TC_PROFILE_CATALOG_MANIFEST={manifest_rel}", "-e", "TC_PROFILE_WORKLOAD_ONLY=1", "-w", "/app/pipeline", CORE_PROFILE_SERVICE, "python", "run_pipeline.py"],
    ]
    if not args.skip_batch:
        commands.append(
            ["docker", "compose", "exec", "-T", "-e", f"TC_PROFILE_RUN_ID={run_id}", "-e", f"TC_PROFILE_MODE={args.mode}", "-e", f"TC_PROFILE_ARTIFACT_DIR={artifact_dir_rel}", "-e", f"TC_PROFILE_BASELINE_VALID={'1' if args.mode == 'baseline' else '0'}", "-e", f"TC_PROFILE_CATALOG_MANIFEST={manifest_rel}", "-e", "TC_PROFILE_WORKLOAD_ONLY=1", "-w", "/app/pipeline", BATCH_PROFILE_SERVICE, "python", "run_batch_enrichment.py"]
        )

    started = time.perf_counter()
    started_at = _utc_now_iso()
    status = "failed"
    error_message = None
    command_segments: list[dict] = []
    try:
        if manifest_package is not None:
            prepare_summary = _prepare_manifest_package_via_docker(manifest_rel, dry_run=False)
            run_manifest["preconditioning"] = prepare_summary
            _write_json(run_dir / "run_manifest.json", run_manifest)
        for command in commands:
            segment_started = time.perf_counter()
            segment_name = "pipeline-batch" if "run_batch_enrichment.py" in command else "pipeline"
            _run_command(command, env=env, cwd=REPO_ROOT, log_path=command_log)
            command_segments.append(
                {
                    "name": segment_name,
                    "command": command,
                    "status": "completed",
                    "elapsed_seconds": round(time.perf_counter() - segment_started, 3),
                }
            )

        quality = _segment_status_from_log(command_log)
        _write_json(
            run_dir / "result.json",
            _build_result_payload(
                run_id=run_id,
                status="commands_completed",
                started_at=started_at,
                finished_at=_utc_now_iso(),
                elapsed_seconds=time.perf_counter() - started,
                include_batch=not args.skip_batch,
                segments=command_segments,
                error_message=None,
                quality=quality,
            ),
        )

        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "collect_soak_metrics.py"),
                "--run-id",
                run_id,
                "--output-dir",
                str(output_root),
                "--api-url",
                args.api_url,
            ],
            cwd=str(REPO_ROOT),
            check=True,
            env=os.environ.copy(),
        )
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "analyze_pipeline_profile.py"),
                "--run-id",
                run_id,
                "--output-dir",
                str(output_root),
            ],
            cwd=str(REPO_ROOT),
            check=True,
            env=os.environ.copy(),
        )
        status = "completed"
        return 0
    except (subprocess.CalledProcessError, OSError) as exc:
        error_message = f"{exc.__class__.__name__}: {exc}"
        if isinstance(exc, subprocess.CalledProcessError):
            if command_segments:
                last = command_segments[-1]
                if last["status"] == "completed":
                    pass
            attempted = "pipeline-batch" if "run_batch_enrichment.py" in (exc.cmd or []) else "pipeline"
            if not command_segments or command_segments[-1]["name"] != attempted:
                command_segments.append(
                    {
                        "name": attempted,
                        "command": exc.cmd,
                        "status": "failed",
                        "elapsed_seconds": 0.0,
                    }
                )
        raise
    finally:
        quality = _segment_status_from_log(command_log)
        _write_json(
            run_dir / "result.json",
            _build_result_payload(
                run_id=run_id,
                status=status,
                started_at=started_at,
                finished_at=_utc_now_iso(),
                elapsed_seconds=time.perf_counter() - started,
                include_batch=not args.skip_batch,
                segments=command_segments,
                error_message=error_message,
                quality=quality,
            ),
        )
        print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": status}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
