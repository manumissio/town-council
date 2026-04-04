#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess


DEFAULT_RESULTS_ROOT = "experiments/results"
DEFAULT_CATALOG_FILE = "experiments/gemma4_quality_checkpoint_cohort_v1.txt"
DEFAULT_RUN_PREFIX = "gemma4_host_metal_quality_checkpoint_v1"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _run(cmd: list[str], *, cwd: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, check=True, capture_output=capture)


def _extract_experiment_dir(stdout: str) -> str:
    start = stdout.rfind("{")
    if start < 0:
        raise RuntimeError("could not find experiment JSON payload in strict-swap stdout")
    payload = json.loads(stdout[start:])
    experiment_dir = payload.get("experiment_dir")
    if not experiment_dir:
        raise RuntimeError("strict-swap output missing experiment_dir")
    return str(experiment_dir)


def _snapshot_run_ids(experiment_dir: Path) -> tuple[str, str]:
    control = json.loads((experiment_dir / "control_snapshot.json").read_text(encoding="utf-8"))
    treatment = json.loads((experiment_dir / "treatment_snapshot.json").read_text(encoding="utf-8"))
    return str(control["run_dir"]), str(treatment["run_dir"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the host-Metal Gemma 4 quality checkpoint experiment.")
    parser.add_argument("--catalog-file", default=DEFAULT_CATALOG_FILE)
    parser.add_argument("--results-root", default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--run-prefix", default=DEFAULT_RUN_PREFIX)
    parser.add_argument("--strict-runner", default="scripts/run_gemma4_host_metal_strict_swap.py")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ollama-binary", default="ollama")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = os.getcwd()
    results_root = Path(repo_root) / args.results_root
    quality_root = results_root / f"{args.run_prefix}_{_utc_stamp()}"
    quality_root.mkdir(parents=True, exist_ok=False)

    completed = _run(
        [
            "python3",
            args.strict_runner,
            "--catalog-file",
            args.catalog_file,
            "--run-prefix",
            args.run_prefix,
            "--results-root",
            args.results_root,
            "--ollama-binary",
            args.ollama_binary,
        ],
        cwd=repo_root,
        capture=True,
    )

    experiment_dir = Path(_extract_experiment_dir(completed.stdout))
    control_run, treatment_run = _snapshot_run_ids(experiment_dir)

    review_dir = quality_root / "review_packet"
    _run(
        [
            "python3",
            "scripts/build_segmentation_review_packet.py",
            "--control-run",
            control_run,
            "--treatment-run",
            treatment_run,
            "--results-root",
            args.results_root,
            "--output-dir",
            str(review_dir),
            "--seed",
            str(args.seed),
        ],
        cwd=repo_root,
    )

    analysis_dir = quality_root / "analysis"
    _run(
        [
            "python3",
            "scripts/analyze_segmentation_quality_checkpoint.py",
            "--control-run",
            control_run,
            "--treatment-run",
            treatment_run,
            "--results-root",
            args.results_root,
            "--output-dir",
            str(analysis_dir),
        ],
        cwd=repo_root,
    )

    manifest = {
        "strict_experiment_dir": str(experiment_dir),
        "control_run": control_run,
        "treatment_run": treatment_run,
        "review_packet_dir": str(review_dir),
        "analysis_dir": str(analysis_dir),
        "catalog_file": args.catalog_file,
    }
    (quality_root / "quality_checkpoint_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"quality_checkpoint_dir": str(quality_root), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
