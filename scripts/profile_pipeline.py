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
from pipeline.run_pipeline import select_catalog_ids_for_processing
from pipeline.tasks import select_catalog_ids_for_summary_hydration


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = "experiments/results/profiling"
DEFAULT_TRIAGE_LIMIT = 25


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _profile_env(*, run_id: str, mode: str, artifact_dir: str, baseline_valid: bool, manifest_path: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TC_PROFILE_RUN_ID"] = run_id
    env["TC_PROFILE_MODE"] = mode
    env["TC_PROFILE_ARTIFACT_DIR"] = artifact_dir
    env["TC_PROFILE_BASELINE_VALID"] = "1" if baseline_valid else "0"
    env["TC_PROFILE_CATALOG_MANIFEST"] = manifest_path
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

    if args.mode == "baseline":
        catalog_ids = _load_manifest_catalog_ids(Path(args.manifest))
    else:
        catalog_ids = _select_triage_catalog_ids(limit=max(1, int(args.limit)), city=args.city)
    if not catalog_ids:
        raise SystemExit("no catalog ids selected for profiling")

    manifest_copy = run_dir / "catalog_manifest.txt"
    _write_catalog_manifest(manifest_copy, catalog_ids)
    provider_counters_before_run = _provider_counters_before_run()

    run_manifest = {
        "run_id": run_id,
        "mode": args.mode,
        "started_at": _utc_now_iso(),
        "baseline_valid": args.mode == "baseline",
        "catalog_ids": catalog_ids,
        "catalog_count": len(catalog_ids),
        "city": args.city,
        "include_batch": not args.skip_batch,
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
    _write_json(run_dir / "run_manifest.json", run_manifest)

    artifact_dir_rel = _path_for_profile_env(run_dir)
    manifest_rel = _path_for_profile_env(manifest_copy)
    env = _profile_env(
        run_id=run_id,
        mode=args.mode,
        artifact_dir=artifact_dir_rel,
        baseline_valid=args.mode == "baseline",
        manifest_path=manifest_rel,
    )

    commands = [
        ["docker", "compose", "run", "--rm", "pipeline", "python", "run_pipeline.py"],
    ]
    if not args.skip_batch:
        commands.append(["docker", "compose", "run", "--rm", "pipeline-batch", "python", "run_batch_enrichment.py"])

    command_log = run_dir / "commands.log"
    started = time.perf_counter()
    status = "failed"
    error_message = None
    try:
        for command in commands:
            _run_command(command, env=env, cwd=REPO_ROOT, log_path=command_log)

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
        raise
    finally:
        _write_json(
            run_dir / "result.json",
            {
                "run_id": run_id,
                "status": status,
                "finished_at": _utc_now_iso(),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "commands": commands,
                "error": error_message,
            },
        )
        print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": status}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
