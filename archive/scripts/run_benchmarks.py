#!/usr/bin/env python3
"""
Run repo benchmarks with reproducible metadata.

Why this exists:
- benchmark numbers are only comparable when we know exactly which code and
  environment produced them
- pytest-benchmark JSON alone is not enough for this repo's evidence contract

Historical note:
- this script is retained for archive/reference purposes only
- it is not a supported active operator entrypoint
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENDPOINTS = [
    ("search_newest", "/search?q=zoning&sort=newest&limit=20"),
    ("search_semantic", "/search/semantic?q=zoning&limit=20"),
    ("metadata", "/metadata"),
    ("people", "/people?limit=50"),
]


def _git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
    ).strip()


def _collect_git_metadata() -> dict[str, object]:
    sha = _git_output("rev-parse", "HEAD")
    short_sha = _git_output("rev-parse", "--short", "HEAD")
    status = _git_output("status", "--short")
    return {
        "commit_sha": sha,
        "commit_short_sha": short_sha,
        "dirty": bool(status),
        "status_short": status.splitlines(),
    }


def _default_output_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "experiments" / "results" / "benchmarks" / timestamp


def _run_pytest_benchmarks(output_dir: Path, pytest_bin: str, extra_args: list[str]) -> dict[str, object]:
    benchmark_json = output_dir / "pytest_benchmark.json"
    cmd = [
        pytest_bin,
        "-q",
        "tests/test_benchmarks.py",
        f"--benchmark-json={benchmark_json}",
        *extra_args,
    ]
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "benchmark_json": str(benchmark_json.relative_to(REPO_ROOT)),
    }


def _probe_endpoint(base_url: str, path: str, samples: int, timeout_seconds: float) -> dict[str, float]:
    durations = []
    for _ in range(samples):
        start = time.perf_counter()
        with urlopen(base_url.rstrip("/") + path, timeout=timeout_seconds) as response:
            response.read()
        durations.append((time.perf_counter() - start) * 1000.0)

    ordered = sorted(durations)
    p95_index = max(0, int(0.95 * len(ordered)) - 1)
    return {
        "samples": samples,
        "p50_ms": round(statistics.median(durations), 2),
        "p95_ms": round(ordered[p95_index], 2),
        "min_ms": round(min(durations), 2),
        "max_ms": round(max(durations), 2),
    }


def _run_endpoint_benchmarks(output_dir: Path, base_url: str, samples: int, timeout_seconds: float) -> dict[str, object]:
    timings = {
        name: _probe_endpoint(base_url, path, samples, timeout_seconds)
        for name, path in DEFAULT_ENDPOINTS
    }
    payload = {
        "base_url": base_url,
        "samples_per_endpoint": samples,
        "timeout_seconds": timeout_seconds,
        "timings": timings,
    }
    (output_dir / "endpoint_timings.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmarks with commit/environment metadata.")
    parser.add_argument("--output-dir", default=None, help="Output directory for benchmark artifacts.")
    parser.add_argument("--pytest-bin", default=str(REPO_ROOT / ".venv" / "bin" / "pytest"))
    parser.add_argument("--skip-pytest-benchmarks", action="store_true")
    parser.add_argument("--base-url", default="http://api:8000", help="Base URL for endpoint timing.")
    parser.add_argument("--skip-endpoint-benchmarks", action="store_true")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("pytest_args", nargs="*", help="Extra args forwarded to pytest benchmark run.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else _default_output_dir()
    if not output_dir.is_absolute():
        output_dir = (REPO_ROOT / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "python": sys.version,
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "git": _collect_git_metadata(),
        "artifacts": {},
    }

    if not args.skip_pytest_benchmarks:
        metadata["artifacts"]["pytest_benchmarks"] = _run_pytest_benchmarks(
            output_dir, args.pytest_bin, args.pytest_args
        )

    if not args.skip_endpoint_benchmarks:
        metadata["artifacts"]["endpoint_timings"] = _run_endpoint_benchmarks(
            output_dir, args.base_url, args.samples, args.timeout_seconds
        )

    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"output_dir": str(output_dir), "metadata_file": str(output_dir / "metadata.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
