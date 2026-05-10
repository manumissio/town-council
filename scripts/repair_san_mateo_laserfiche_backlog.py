#!/usr/bin/env python3
from __future__ import annotations

import argparse
import requests
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

from pipeline.config import DOWNLOAD_TIMEOUT_SECONDS
from scripts import laserfiche_repair_downloads as _download_impl
from scripts.laserfiche_repair_backlog import apply_repairs as _apply_repairs
from scripts.laserfiche_repair_backlog import select_targets as _select_targets
from scripts.laserfiche_repair_contracts import GENERATED_PDF_FETCH_RETRIES
from scripts.laserfiche_repair_contracts import GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS
from scripts.laserfiche_repair_contracts import PDF_TRANSITION_POLL_INTERVAL_SECONDS
from scripts.laserfiche_repair_contracts import PDF_TRANSITION_TIMEOUT_SECONDS
from scripts.laserfiche_repair_contracts import RETRYABLE_FAILURE_REASONS
from scripts.laserfiche_repair_contracts import THREAD_STATE as _THREAD_STATE
from scripts.laserfiche_repair_contracts import RepairNonRetryableError
from scripts.laserfiche_repair_contracts import RepairRetryableError
from scripts.laserfiche_repair_contracts import RepairTarget
from scripts.laserfiche_repair_contracts import coerce_bool as _coerce_bool
from scripts.laserfiche_repair_contracts import electronic_file_url as _electronic_file_url
from scripts.laserfiche_repair_contracts import failure_reason as _failure_reason
from scripts.laserfiche_repair_contracts import parse_docview_url as _parse_docview_url
from scripts.laserfiche_repair_contracts import parse_electronic_file_url as _parse_electronic_file_url
from scripts.laserfiche_repair_contracts import target_path as _target_path
from scripts.laserfiche_repair_contracts import url_to_md5 as _url_to_md5
from scripts.laserfiche_repair_downloads import build_page_range as _build_page_range
from scripts.laserfiche_repair_downloads import document_supports_electronic_file as _document_supports_electronic_file
from scripts.laserfiche_repair_downloads import fetch_basic_document_info as _fetch_basic_document_info
from scripts import laserfiche_repair_pdf_io as _pdf_io
from scripts.laserfiche_repair_reporting import _print_dry_run
from scripts.laserfiche_repair_reporting import _print_finish
from scripts.laserfiche_repair_reporting import _print_lane_selection
from scripts.laserfiche_repair_reporting import _print_start
from scripts.operator_cli import nonnegative_int as _nonnegative_int, positive_int as _positive_int

_file_has_pdf_eof_marker = _pdf_io.file_has_pdf_eof_marker
_file_has_pdf_signature = _pdf_io.file_has_pdf_signature
_is_valid_pdf_artifact = _pdf_io.is_valid_pdf_artifact
_iter_pdf_chunks = _pdf_io.iter_pdf_chunks
_laserfiche_headers = _pdf_io.laserfiche_headers
_raise_for_invalid_pdf_response = _pdf_io.raise_for_invalid_pdf_response
_worker_session = _pdf_io.worker_session
_write_validated_pdf_response = _pdf_io.write_validated_pdf_response


def _sync_helper_test_hooks() -> None:
    _download_impl.worker_session = _worker_session
    _download_impl.fetch_basic_document_info = _fetch_basic_document_info
    _download_impl.DOWNLOAD_TIMEOUT_SECONDS = DOWNLOAD_TIMEOUT_SECONDS
    _download_impl.GENERATED_PDF_FETCH_RETRIES = GENERATED_PDF_FETCH_RETRIES
    _download_impl.GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS = GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS
    _download_impl.PDF_TRANSITION_POLL_INTERVAL_SECONDS = PDF_TRANSITION_POLL_INTERVAL_SECONDS


def _classify_target(target: RepairTarget) -> RepairTarget:
    _sync_helper_test_hooks()
    return _download_impl.classify_target(target)


def _classify_targets(targets: list[RepairTarget], *, workers: int) -> list[RepairTarget]:
    _sync_helper_test_hooks()
    return _download_impl.classify_targets(targets, workers=workers)


def _download_generated_pdf(*args: object, **kwargs: object) -> int:
    _sync_helper_test_hooks()
    if "pdf_transition_timeout_seconds" not in kwargs:
        kwargs["pdf_transition_timeout_seconds"] = PDF_TRANSITION_TIMEOUT_SECONDS
    return _download_impl.download_generated_pdf(*args, **kwargs)


def _download_repaired_pdf(*args: object, **kwargs: object) -> dict[str, object]:
    _sync_helper_test_hooks()
    if "pdf_transition_timeout_seconds" not in kwargs:
        kwargs["pdf_transition_timeout_seconds"] = PDF_TRANSITION_TIMEOUT_SECONDS
    return _download_impl.download_repaired_pdf(*args, **kwargs)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair poisoned San Mateo Laserfiche agenda rows in place")
    parser.add_argument("--city", default="san_mateo")
    parser.add_argument("--limit", type=_positive_int, default=None)
    parser.add_argument("--resume-after-id", type=_nonnegative_int, default=None, dest="resume_after_id")
    parser.add_argument("--workers", type=_positive_int, default=4)
    parser.add_argument("--generated-pdf-workers", type=_positive_int, default=2, dest="generated_pdf_workers")
    parser.add_argument("--apply-batch-size", type=_positive_int, default=200)
    parser.add_argument("--pdf-transition-timeout", type=_positive_int, default=PDF_TRANSITION_TIMEOUT_SECONDS)
    parser.add_argument("--retry-only", action="store_true")
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--salvage-bad-electronicfile", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    targets = _select_targets(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        salvage_bad_electronicfile=args.salvage_bad_electronicfile,
    )
    _print_start(args, len(targets))
    if not targets:
        return 0

    classified_targets = _classify_targets(targets, workers=max(args.workers, args.generated_pdf_workers))
    classified_targets.sort(key=lambda target: target.catalog_id)
    _print_lane_selection(args.city, classified_targets)

    if args.dry_run:
        _print_dry_run(args.city, classified_targets)
        return 0

    return _download_apply_and_report(args, targets, classified_targets)


def _download_apply_and_report(
    args: argparse.Namespace,
    targets: list[RepairTarget],
    classified_targets: list[RepairTarget],
) -> int:
    state: dict[str, object] = {
        "repairs": [],
        "failed": 0,
        "total_updated": 0,
        "total_skipped_duplicate_hash": 0,
        "retrieval_counts": Counter(),
        "failure_counts": Counter(),
        "retry_stats": Counter(),
        "retry_targets": [],
    }

    if args.retry_only:
        state["retry_targets"] = classified_targets
    else:
        fast_targets = [target for target in classified_targets if target.preferred_method == "electronic_file"]
        generated_targets = [target for target in classified_targets if target.preferred_method == "generated_pdf"]
        _run_lane(args, state, "fast", fast_targets, workers=args.workers, force_generated_pdf=False, collect_retryables=True)
        _run_lane(
            args,
            state,
            "generated_pdf",
            generated_targets,
            workers=args.generated_pdf_workers,
            force_generated_pdf=True,
            collect_retryables=True,
        )
    _run_lane(
        args,
        state,
        "retry",
        state["retry_targets"],
        workers=args.generated_pdf_workers,
        force_generated_pdf=True,
        collect_retryables=False,
        pdf_transition_timeout_seconds=max(args.pdf_transition_timeout, PDF_TRANSITION_TIMEOUT_SECONDS * 2),
    )

    _flush_repairs(args, state)
    _print_finish(args, state, targets, classified_targets)
    return 0 if int(state["failed"]) == 0 else 1


def _run_lane(
    args: argparse.Namespace,
    state: dict[str, object],
    lane_name: str,
    lane_targets: list[RepairTarget],
    *,
    workers: int,
    force_generated_pdf: bool,
    collect_retryables: bool,
    pdf_transition_timeout_seconds: int | None = None,
) -> None:
    if not lane_targets:
        return
    timeout = pdf_transition_timeout_seconds or args.pdf_transition_timeout
    print(
        f"[{args.city}] repair_lane_start lane={lane_name} selected={len(lane_targets)} "
        f"workers={workers} force_generated_pdf={force_generated_pdf} pdf_transition_timeout={timeout}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_repaired_pdf, target, pdf_transition_timeout_seconds=timeout, force_generated_pdf=force_generated_pdf): target
            for target in lane_targets
        }
        for future in as_completed(futures):
            target = futures[future]
            try:
                _record_repair(args, state, target, future.result())
            except Exception as exc:
                _record_failure(args, state, target, exc, collect_retryables)


def _record_repair(
    args: argparse.Namespace,
    state: dict[str, object],
    target: RepairTarget,
    repair: dict[str, object],
) -> None:
    retrieval_counts: Counter[str] = state["retrieval_counts"]
    retry_stats: Counter[str] = state["retry_stats"]
    repairs: list[dict[str, object]] = state["repairs"]
    retrieval_counts[str(repair.get("retrieval_type") or "unknown")] += 1
    fetch_retries = int(repair.get("fetch_retries") or 0)
    if fetch_retries > 0:
        retry_stats["generated_pdf_fetch_retries"] += fetch_retries
    repairs.append(repair)
    print(
        f"[{args.city}] repair_downloaded catalog_id={target.catalog_id} path={repair['path']} "
        f"size={repair['size']} method={repair['method']} fetch_retries={fetch_retries}",
        flush=True,
    )
    if len(repairs) >= args.apply_batch_size:
        _flush_repairs(args, state)


def _record_failure(
    args: argparse.Namespace,
    state: dict[str, object],
    target: RepairTarget,
    exc: Exception,
    collect_retryables: bool,
) -> None:
    reason = _failure_reason(exc)
    failure_counts: Counter[str] = state["failure_counts"]
    retry_stats: Counter[str] = state["retry_stats"]
    failure_counts[reason] += 1
    if reason == "generated_pdf_html_retryable":
        retry_stats["generated_pdf_html_retryable"] += 1
    if reason in {"remote_disconnected", "incomplete_read", "connection_error", "read_timeout"}:
        retry_stats["generated_pdf_transport_retryable"] += 1
    if reason == "invalid_partial_pdf":
        retry_stats["generated_pdf_invalid_partial_pdf"] += 1
    if collect_retryables and reason in RETRYABLE_FAILURE_REASONS:
        retry_targets: list[RepairTarget] = state["retry_targets"]
        retry_targets.append(target)
    else:
        state["failed"] = int(state["failed"]) + 1
    print(f"[{args.city}] repair_failed catalog_id={target.catalog_id} reason={reason} error={exc}", flush=True)


def _flush_repairs(args: argparse.Namespace, state: dict[str, object]) -> None:
    repairs: list[dict[str, object]] = state["repairs"]
    if not repairs:
        return
    counts = _apply_repairs(repairs, reindex=args.reindex)
    state["total_updated"] = int(state["total_updated"]) + counts["updated"]
    state["total_skipped_duplicate_hash"] = int(state["total_skipped_duplicate_hash"]) + counts["skipped_duplicate_hash"]
    print(
        f"[{args.city}] repair_batch_applied updated={counts['updated']} "
        f"skipped_duplicate_hash={counts['skipped_duplicate_hash']}",
        flush=True,
    )
    state["repairs"] = []


if __name__ == "__main__":
    raise SystemExit(main())
