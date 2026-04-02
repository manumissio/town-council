#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from pipeline.profile_manifest import (
    DEFAULT_PHASE_QUOTAS,
    sidecar_path_for_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "profiling" / "manifests"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a representative profiling manifest package.")
    parser.add_argument("--name", required=True, help="Manifest base name without extension.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--write", action="store_true", help="Write the manifest package to profiling/manifests.")
    parser.add_argument("--extract-quota", type=int, default=DEFAULT_PHASE_QUOTAS["extract"])
    parser.add_argument("--segment-quota", type=int, default=DEFAULT_PHASE_QUOTAS["segment"])
    parser.add_argument("--summary-quota", type=int, default=DEFAULT_PHASE_QUOTAS["summary"])
    parser.add_argument("--entity-quota", type=int, default=DEFAULT_PHASE_QUOTAS["entity"])
    parser.add_argument("--org-quota", type=int, default=DEFAULT_PHASE_QUOTAS["org"])
    parser.add_argument("--people-quota", type=int, default=DEFAULT_PHASE_QUOTAS["people"])
    return parser.parse_args(argv)


def _manifest_paths(output_dir: Path, name: str) -> tuple[Path, Path]:
    manifest_path = output_dir / f"{name}.txt"
    return manifest_path, sidecar_path_for_manifest(manifest_path)


def _write_manifest_files(manifest_path: Path, sidecar_path: Path, package: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "".join(f"{int(cid)}\n" for cid in package["catalog_ids"]),
        encoding="utf-8",
    )
    sidecar_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_manifest_package_via_docker(*, name: str, quotas: dict[str, int]) -> dict:
    statement = (
        "import json; "
        "from pipeline.profile_manifest import build_manifest_package; "
        f"package=build_manifest_package({name!r}, quotas={quotas!r}); "
        "print(json.dumps(package, sort_keys=True))"
    )
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-w",
        "/app",
        "worker",
        "python",
        "-c",
        statement,
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=True,
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
    raise RuntimeError("expected JSON object from manifest builder")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir

    package = _build_manifest_package_via_docker(
        name=args.name,
        quotas={
            "extract": args.extract_quota,
            "segment": args.segment_quota,
            "summary": args.summary_quota,
            "entity": args.entity_quota,
            "org": args.org_quota,
            "people": args.people_quota,
        },
    )
    manifest_path, sidecar_path = _manifest_paths(output_dir, args.name)
    if args.write:
        _write_manifest_files(manifest_path, sidecar_path, package)

    report = {
        "manifest_name": args.name,
        "manifest_path": str(manifest_path),
        "sidecar_path": str(sidecar_path),
        "write": bool(args.write),
        "catalog_count": len(package["catalog_ids"]),
        "phase_candidates": package["phase_candidates"],
        "phase_selected_counts": {key: len(value) for key, value in package["strata"].items()},
        "expected_phase_coverage": package["expected_phase_coverage"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
