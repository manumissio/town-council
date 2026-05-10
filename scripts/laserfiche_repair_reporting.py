from __future__ import annotations

import argparse
from collections import Counter

from scripts.laserfiche_repair_contracts import RepairTarget


def _print_start(args: argparse.Namespace, selected: int) -> None:
    print(
        f"[{args.city}] repair_targets selected={selected} resume_after_id={args.resume_after_id} "
        f"workers={args.workers} generated_pdf_workers={args.generated_pdf_workers} retry_only={args.retry_only} "
        f"dry_run={args.dry_run} salvage_bad_electronicfile={args.salvage_bad_electronicfile}",
        flush=True,
    )


def _print_lane_selection(city: str, targets: list[RepairTarget]) -> None:
    preferred_counts = Counter(target.preferred_method for target in targets)
    print(
        f"[{city}] repair_lane_selection electronic_file={preferred_counts.get('electronic_file', 0)} "
        f"generated_pdf={preferred_counts.get('generated_pdf', 0)}",
        flush=True,
    )


def _print_dry_run(city: str, targets: list[RepairTarget]) -> None:
    for target in targets[:5]:
        print(
            f"[{city}] dry_run catalog_id={target.catalog_id} old_url={target.old_url} "
            f"new_url={target.new_url} preferred_method={target.preferred_method}",
            flush=True,
        )


def _print_finish(
    args: argparse.Namespace,
    state: dict[str, object],
    targets: list[RepairTarget],
    classified_targets: list[RepairTarget],
) -> None:
    last_catalog_id = max((target.catalog_id for target in classified_targets), default=args.resume_after_id)
    print(
        f"[{args.city}] repair_finish downloaded={len(targets) - int(state['failed'])} failed={state['failed']} "
        f"updated={state['total_updated']} skipped_duplicate_hash={state['total_skipped_duplicate_hash']} "
        f"retrieval_counts={dict(sorted(state['retrieval_counts'].items()))} "
        f"failure_counts={dict(sorted(state['failure_counts'].items()))} "
        f"retry_stats={dict(sorted(state['retry_stats'].items()))} resume_after_id={last_catalog_id}",
        flush=True,
    )
