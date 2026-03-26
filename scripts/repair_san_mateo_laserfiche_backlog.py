#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http.client import IncompleteRead, RemoteDisconnected
from typing import Iterator

import requests
from sqlalchemy import and_
from pipeline.city_scope import source_aliases_for_city
from pipeline.config import DOWNLOAD_TIMEOUT_SECONDS
from pipeline.db_session import db_session
from pipeline.indexer import reindex_catalog
from pipeline.models import AgendaItem, Catalog, Document, Event, SemanticEmbedding


DOCVIEW_RE = re.compile(r"/DocView\.aspx\?id=(?P<entry_id>\d+)&repo=(?P<repo>[^&]+)", re.IGNORECASE)
ELECTRONIC_FILE_RE = re.compile(
    r"/ElectronicFile\.aspx\?docid=(?P<entry_id>\d+)&repo=(?P<repo>[^&]+)",
    re.IGNORECASE,
)
PDF_TRANSITION_TIMEOUT_SECONDS = 30
PDF_TRANSITION_POLL_INTERVAL_SECONDS = 1
GENERATED_PDF_FETCH_RETRIES = 3
GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS = 1
RETRYABLE_FAILURE_REASONS = {
    "timed_out",
    "token_missing",
    "remote_disconnected",
    "incomplete_read",
    "connection_error",
    "read_timeout",
    "generated_pdf_html_retryable",
    "invalid_partial_pdf",
}
_THREAD_STATE = threading.local()


def _url_to_md5(value: str) -> str:
    return hashlib.md5((value or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RepairTarget:
    catalog_id: int
    old_url: str
    location: str | None
    mode: str = "docview"
    entry_id: int | None = None
    repo: str | None = None
    new_url: str | None = None
    preferred_method: str = "electronic_file"
    page_count: int | None = None


class RepairRetryableError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class RepairNonRetryableError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return parsed


def _parse_docview_url(url: str) -> tuple[int, str]:
    match = DOCVIEW_RE.search(url or "")
    if not match:
        raise ValueError(f"Unsupported Laserfiche DocView URL: {url!r}")
    return int(match.group("entry_id")), match.group("repo")


def _parse_electronic_file_url(url: str) -> tuple[int, str]:
    match = ELECTRONIC_FILE_RE.search(url or "")
    if not match:
        raise ValueError(f"Unsupported Laserfiche ElectronicFile URL: {url!r}")
    return int(match.group("entry_id")), match.group("repo")


def _electronic_file_url(entry_id: int, repo: str) -> str:
    return f"https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid={entry_id}&repo={repo}"


def _target_path(existing_location: str | None, url_hash: str) -> tuple[str, str]:
    base_dir = os.path.dirname(existing_location) if existing_location else ""
    if not base_dir:
        raise ValueError("Catalog has no existing directory to store repaired PDF")
    filename = f"{url_hash}.pdf"
    return os.path.join(base_dir, filename), filename


def _file_has_pdf_signature(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(5) == b"%PDF-"
    except OSError:
        return False


def _file_has_pdf_eof_marker(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 2048))
            tail = fh.read()
        return b"%%EOF" in tail
    except OSError:
        return False


def _is_valid_pdf_artifact(path: str | None) -> bool:
    if not path or not os.path.exists(path):
        return False
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False
    return _file_has_pdf_signature(path)


def _laserfiche_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Lf-Suppress-Login-Redirect": "1",
    }


def _worker_session() -> requests.Session:
    session = getattr(_THREAD_STATE, "session", None)
    if session is None:
        session = requests.Session()
        session.trust_env = False
        _THREAD_STATE.session = session
    return session


def _raise_for_invalid_pdf_response(response: requests.Response, *, catalog_id: int) -> None:
    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/pdf":
        body = (response.text or "")[:2000]
        lowered = body.lower()
        if "laserfiche" in lowered or "docview" in lowered or "electronicfile" in lowered or "portal" in lowered:
            raise RepairRetryableError(
                "generated_pdf_html_retryable",
                f"Retryable HTML interstitial returned for catalog {catalog_id}",
            )
        raise RepairNonRetryableError(
            "unexpected_content_type",
            f"Unexpected content type {content_type!r} for catalog {catalog_id}",
        )


def _iter_pdf_chunks(response: requests.Response) -> Iterator[bytes]:
    try:
        yield from response.iter_content(chunk_size=1024 * 256)
    except requests.exceptions.ReadTimeout as exc:
        raise RepairRetryableError("read_timeout", f"Read timeout while downloading generated PDF: {exc}") from exc
    except requests.exceptions.ChunkedEncodingError as exc:
        message = str(exc).lower()
        if "incompleteread" in message:
            raise RepairRetryableError("incomplete_read", f"Incomplete generated PDF response: {exc}") from exc
        raise RepairRetryableError("connection_error", f"Chunked response failed for generated PDF: {exc}") from exc
    except requests.exceptions.ConnectionError as exc:
        message = str(exc).lower()
        if "remotedisconnected" in message or isinstance(getattr(exc, "__cause__", None), RemoteDisconnected):
            raise RepairRetryableError("remote_disconnected", f"Remote disconnected during generated PDF fetch: {exc}") from exc
        if "incompleteread" in message or isinstance(getattr(exc, "__cause__", None), IncompleteRead):
            raise RepairRetryableError("incomplete_read", f"Incomplete generated PDF response: {exc}") from exc
        raise RepairRetryableError("connection_error", f"Connection failed during generated PDF fetch: {exc}") from exc


def _write_validated_pdf_response(
    response: requests.Response,
    *,
    temp_path: str,
    final_path: str,
    catalog_id: int,
) -> int:
    _raise_for_invalid_pdf_response(response, catalog_id=catalog_id)
    try:
        with open(temp_path, "wb") as fh:
            for chunk in _iter_pdf_chunks(response):
                if chunk:
                    fh.write(chunk)

        size = os.path.getsize(temp_path)
        if size <= 0:
            raise RepairRetryableError("invalid_partial_pdf", f"Downloaded zero-byte PDF for catalog {catalog_id}")
        if not _file_has_pdf_signature(temp_path):
            raise RepairRetryableError("invalid_partial_pdf", f"Downloaded invalid PDF bytes for catalog {catalog_id}")
        if not _file_has_pdf_eof_marker(temp_path):
            raise RepairRetryableError("invalid_partial_pdf", f"Downloaded truncated PDF for catalog {catalog_id}")

        os.replace(temp_path, final_path)
        return size
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _fetch_basic_document_info(
    session: requests.Session,
    *,
    entry_id: int,
    repo: str,
) -> dict[str, object]:
    response = session.post(
        "https://portal.laserfiche.com/Portal/DocumentService.aspx/GetBasicDocumentInfo",
        headers=_laserfiche_headers(),
        json={"repoName": repo, "entryId": entry_id},
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"Laserfiche basic document info missing for entry {entry_id}")
    return data


def _build_page_range(page_count: int) -> str:
    if page_count <= 0:
        raise ValueError("Laserfiche document has no pages to export")
    return f"1 - {page_count}"


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    return None


def _document_supports_electronic_file(info: dict[str, object]) -> bool:
    for key in (
        "hasEdoc",
        "hasEDoc",
        "isEdoc",
        "isEDoc",
        "isElectronicDoc",
        "hasElectronicFile",
        "electronicDocument",
        "electronicFile",
    ):
        if key in info:
            coerced = _coerce_bool(info.get(key))
            if coerced is not None:
                return coerced

    for key in ("edocUrl", "electronicFileUrl", "electronicUrl"):
        value = str(info.get(key) or "").strip()
        if value:
            return True

    return False


def _classify_target(target: RepairTarget) -> RepairTarget:
    if target.mode == "salvage":
        entry_id, repo = _parse_electronic_file_url(target.old_url)
        new_url = target.old_url
    else:
        entry_id, repo = _parse_docview_url(target.old_url)
        new_url = _electronic_file_url(entry_id, repo)

    info: dict[str, object] = {}
    try:
        info = _fetch_basic_document_info(_worker_session(), entry_id=entry_id, repo=repo)
    except Exception:
        info = {}

    page_count = int(info.get("pageCount") or 0) if info else 0
    preferred_method = "electronic_file"
    if target.mode != "salvage" and not _document_supports_electronic_file(info):
        preferred_method = "generated_pdf"

    return RepairTarget(
        catalog_id=target.catalog_id,
        old_url=target.old_url,
        location=target.location,
        mode=target.mode,
        entry_id=entry_id,
        repo=repo,
        new_url=new_url,
        preferred_method=preferred_method,
        page_count=page_count if page_count > 0 else None,
    )


def _download_generated_pdf(
    session: requests.Session,
    *,
    entry_id: int,
    repo: str,
    page_count: int,
    temp_path: str,
    final_path: str,
    catalog_id: int,
    pdf_transition_timeout_seconds: int = PDF_TRANSITION_TIMEOUT_SECONDS,
) -> int:
    page_range = _build_page_range(page_count).replace(" ", "+")
    generate = session.post(
        f"https://portal.laserfiche.com/Portal/GeneratePDF10.aspx?key={entry_id}&PageRange={page_range}&Watermark=0&repo={repo}",
        headers=_laserfiche_headers(),
        data="{}",
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    generate.raise_for_status()
    token = (generate.text.split("\n", 1)[0] or "").strip().replace("\r", "")
    if not token:
        raise ValueError(f"Laserfiche PDF generation token missing for catalog {catalog_id}")

    deadline = time.time() + pdf_transition_timeout_seconds
    while True:
        progress = session.post(
            "https://portal.laserfiche.com/Portal/DocumentService.aspx/PDFTransition",
            headers=_laserfiche_headers(),
            json={"Key": token},
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        )
        progress.raise_for_status()
        progress_payload = progress.json().get("data") or {}
        if progress_payload.get("finished"):
            if not progress_payload.get("success"):
                raise ValueError(
                    f"Laserfiche PDF generation failed for catalog {catalog_id}: {progress_payload.get('errMsg') or 'unknown error'}"
                )
            break
        if time.time() >= deadline:
            raise ValueError(f"Laserfiche PDF generation timed out for catalog {catalog_id}")
        time.sleep(PDF_TRANSITION_POLL_INTERVAL_SECONDS)

    last_error: Exception | None = None
    for attempt in range(1, GENERATED_PDF_FETCH_RETRIES + 1):
        try:
            download = session.get(
                f"https://portal.laserfiche.com/Portal/PDF10/{token}/{entry_id}",
                stream=True,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
            download.raise_for_status()
            size = _write_validated_pdf_response(
                download,
                temp_path=temp_path,
                final_path=final_path,
                catalog_id=catalog_id,
            )
            setattr(_THREAD_STATE, "last_generated_pdf_fetch_retries", attempt - 1)
            return size
        except requests.exceptions.ReadTimeout as exc:
            last_error = RepairRetryableError("read_timeout", f"Read timeout while fetching generated PDF: {exc}")
        except requests.exceptions.ConnectionError as exc:
            message = str(exc).lower()
            if "remotedisconnected" in message:
                last_error = RepairRetryableError("remote_disconnected", f"Remote disconnected while fetching generated PDF: {exc}")
            elif "incompleteread" in message:
                last_error = RepairRetryableError("incomplete_read", f"Incomplete generated PDF response: {exc}")
            else:
                last_error = RepairRetryableError("connection_error", f"Connection error while fetching generated PDF: {exc}")
        except RepairRetryableError as exc:
            last_error = exc
        if attempt < GENERATED_PDF_FETCH_RETRIES:
            time.sleep(GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS * attempt)
    assert last_error is not None
    raise last_error


def _select_targets(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    salvage_bad_electronicfile: bool = False,
) -> list[RepairTarget]:
    with db_session() as session:
        query = (
            session.query(Catalog.id, Catalog.url, Catalog.location)
            .join(Document, Document.catalog_id == Catalog.id)
            .join(Event, Event.id == Document.event_id)
            .outerjoin(AgendaItem, AgendaItem.catalog_id == Catalog.id)
            .filter(
                Event.source.in_(sorted(source_aliases_for_city(city))),
                Document.category == "agenda",
                Catalog.summary.is_(None),
                AgendaItem.id.is_(None),
            )
            .distinct()
            .order_by(Catalog.id)
        )
        if salvage_bad_electronicfile:
            query = query.filter(
                Catalog.url.ilike("%/ElectronicFile.aspx%"),
                Catalog.content.is_(None),
            )
        else:
            query = query.filter(Catalog.url.ilike("%/DocView.aspx%"))
        if resume_after_id is not None:
            query = query.filter(Catalog.id > resume_after_id)
        if limit is not None:
            query = query.limit(limit)
        rows = query.all()
    targets = [
        RepairTarget(
            catalog_id=row[0],
            old_url=row[1],
            location=row[2],
            mode="salvage" if salvage_bad_electronicfile else "docview",
        )
        for row in rows
    ]
    if salvage_bad_electronicfile:
        return [target for target in targets if not _is_valid_pdf_artifact(target.location)]
    return targets


def _classify_targets(targets: list[RepairTarget], *, workers: int) -> list[RepairTarget]:
    if not targets:
        return []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return [future.result() for future in as_completed([executor.submit(_classify_target, target) for target in targets])]


def _failure_reason(exc: Exception) -> str:
    explicit_reason = getattr(exc, "reason", None)
    if isinstance(explicit_reason, str) and explicit_reason:
        return explicit_reason
    lowered = str(exc).strip().lower()
    if "timed out" in lowered:
        return "timed_out"
    if "token missing" in lowered:
        return "token_missing"
    if "unexpected content type" in lowered:
        return "unexpected_content_type"
    if "zero-byte" in lowered:
        return "zero_byte"
    if "invalid pdf" in lowered:
        return "invalid_pdf"
    return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_") or type(exc).__name__.lower()


def _download_repaired_pdf(
    target: RepairTarget,
    *,
    pdf_transition_timeout_seconds: int = PDF_TRANSITION_TIMEOUT_SECONDS,
    force_generated_pdf: bool = False,
) -> dict[str, object]:
    entry_id = target.entry_id
    repo = target.repo
    new_url = target.new_url
    if entry_id is None or repo is None or new_url is None:
        target = _classify_target(target)
        entry_id = target.entry_id
        repo = target.repo
        new_url = target.new_url

    assert entry_id is not None
    assert repo is not None
    assert new_url is not None
    new_hash = _url_to_md5(new_url)
    path, filename = _target_path(target.location, new_hash)
    temp_path = f"{path}.tmp.{target.catalog_id}"
    setattr(_THREAD_STATE, "last_generated_pdf_fetch_retries", 0)

    session = _worker_session()
    direct_error: Exception | None = None
    preferred_method = "generated_pdf" if force_generated_pdf else target.preferred_method
    if preferred_method == "electronic_file":
        try:
            response = session.get(new_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
            response.raise_for_status()
            size = _write_validated_pdf_response(
                response,
                temp_path=temp_path,
                final_path=path,
                catalog_id=target.catalog_id,
            )
            return {
                "catalog_id": target.catalog_id,
                "new_url": new_url,
                "new_hash": new_hash,
                "path": path,
                "filename": filename,
                "size": size,
                "method": "electronic_file",
                "retrieval_type": "electronic_file",
            }
        except (RepairRetryableError, RepairNonRetryableError, requests.RequestException, ValueError) as exc:
            direct_error = exc

    viewer_url = f"https://portal.laserfiche.com/Portal/DocView.aspx?id={entry_id}&repo={repo}"
    viewer = session.get(viewer_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    viewer.raise_for_status()
    page_count = int(target.page_count or 0)
    if page_count <= 0:
        info = _fetch_basic_document_info(session, entry_id=entry_id, repo=repo)
        page_count = int(info.get("pageCount") or 0)
    size = _download_generated_pdf(
        session,
        entry_id=entry_id,
        repo=repo,
        page_count=page_count,
        temp_path=temp_path,
        final_path=path,
        catalog_id=target.catalog_id,
        pdf_transition_timeout_seconds=pdf_transition_timeout_seconds,
    )
    return {
        "catalog_id": target.catalog_id,
        "new_url": new_url,
        "new_hash": new_hash,
        "path": path,
        "filename": filename,
        "size": size,
        "method": f"generated_pdf_after_{type(direct_error).__name__}" if direct_error else "generated_pdf",
        "retrieval_type": "generated_pdf",
        "fetch_retries": int(getattr(_THREAD_STATE, "last_generated_pdf_fetch_retries", 0)),
    }


def _apply_repairs(repairs: list[dict[str, object]], *, reindex: bool) -> dict[str, int]:
    counts = {"updated": 0, "skipped_duplicate_hash": 0}
    reindex_ids: list[int] = []

    with db_session() as session:
        for repair in repairs:
            catalog_id = int(repair["catalog_id"])
            new_hash = str(repair["new_hash"])
            existing = (
                session.query(Catalog.id)
                .filter(Catalog.url_hash == new_hash, Catalog.id != catalog_id)
                .first()
            )
            if existing:
                counts["skipped_duplicate_hash"] += 1
                continue

            catalog = session.get(Catalog, catalog_id)
            if not catalog:
                continue

            catalog.url = str(repair["new_url"])
            catalog.url_hash = new_hash
            catalog.location = str(repair["path"])
            catalog.filename = str(repair["filename"])

            catalog.content = None
            catalog.content_hash = None
            catalog.extraction_status = "pending"
            catalog.extraction_attempted_at = None
            catalog.extraction_attempt_count = 0
            catalog.extraction_error = None

            catalog.summary = None
            catalog.summary_source_hash = None
            catalog.summary_extractive = None
            catalog.entities = None
            catalog.topics = None
            catalog.topics_source_hash = None

            catalog.agenda_segmentation_status = None
            catalog.agenda_segmentation_attempted_at = None
            catalog.agenda_segmentation_item_count = None
            catalog.agenda_segmentation_error = None

            session.query(SemanticEmbedding).filter(SemanticEmbedding.catalog_id == catalog_id).delete(
                synchronize_session=False
            )
            session.query(Document).filter(
                and_(Document.catalog_id == catalog_id, Document.category == "agenda")
            ).update(
                {
                    Document.url: str(repair["new_url"]),
                    Document.url_hash: new_hash,
                },
                synchronize_session=False,
            )

            counts["updated"] += 1
            if reindex:
                reindex_ids.append(catalog_id)

        session.commit()

    for catalog_id in reindex_ids:
        reindex_catalog(catalog_id)

    return counts


def main() -> int:
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
    args = parser.parse_args()

    targets = _select_targets(
        args.city,
        limit=args.limit,
        resume_after_id=args.resume_after_id,
        salvage_bad_electronicfile=args.salvage_bad_electronicfile,
    )
    print(
        f"[{args.city}] repair_targets selected={len(targets)} "
        f"resume_after_id={args.resume_after_id} workers={args.workers} "
        f"generated_pdf_workers={args.generated_pdf_workers} retry_only={args.retry_only} "
        f"dry_run={args.dry_run} salvage_bad_electronicfile={args.salvage_bad_electronicfile}",
        flush=True,
    )
    if not targets:
        return 0

    classified_targets = _classify_targets(targets, workers=max(args.workers, args.generated_pdf_workers))
    classified_targets.sort(key=lambda target: target.catalog_id)
    preferred_counts = Counter(target.preferred_method for target in classified_targets)
    print(
        f"[{args.city}] repair_lane_selection electronic_file={preferred_counts.get('electronic_file', 0)} "
        f"generated_pdf={preferred_counts.get('generated_pdf', 0)}",
        flush=True,
    )

    if args.dry_run:
        for target in classified_targets[:5]:
            print(
                f"[{args.city}] dry_run catalog_id={target.catalog_id} "
                f"old_url={target.old_url} new_url={target.new_url} preferred_method={target.preferred_method}",
                flush=True,
            )
        return 0

    repairs: list[dict[str, object]] = []
    failed = 0
    total_updated = 0
    total_skipped_duplicate_hash = 0
    retrieval_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    generated_pdf_retry_stats: Counter[str] = Counter()
    retry_targets: list[RepairTarget] = []

    def _flush_repairs() -> None:
        nonlocal repairs, total_updated, total_skipped_duplicate_hash
        if not repairs:
            return
        counts = _apply_repairs(repairs, reindex=args.reindex)
        total_updated += counts["updated"]
        total_skipped_duplicate_hash += counts["skipped_duplicate_hash"]
        print(
            f"[{args.city}] repair_batch_applied updated={counts['updated']} "
            f"skipped_duplicate_hash={counts['skipped_duplicate_hash']}",
            flush=True,
        )
        repairs = []

    def _run_lane(
        lane_name: str,
        lane_targets: list[RepairTarget],
        *,
        workers: int,
        force_generated_pdf: bool,
        collect_retryables: bool,
        pdf_transition_timeout_seconds: int,
    ) -> None:
        nonlocal failed, repairs
        if not lane_targets:
            return
        print(
            f"[{args.city}] repair_lane_start lane={lane_name} selected={len(lane_targets)} "
            f"workers={workers} force_generated_pdf={force_generated_pdf} "
            f"pdf_transition_timeout={pdf_transition_timeout_seconds}",
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _download_repaired_pdf,
                    target,
                    pdf_transition_timeout_seconds=pdf_transition_timeout_seconds,
                    force_generated_pdf=force_generated_pdf,
                ): target
                for target in lane_targets
            }
            for future in as_completed(futures):
                target = futures[future]
                try:
                    repair = future.result()
                    retrieval_counts[str(repair.get("retrieval_type") or "unknown")] += 1
                    fetch_retries = int(repair.get("fetch_retries") or 0)
                    if fetch_retries > 0:
                        generated_pdf_retry_stats["generated_pdf_fetch_retries"] += fetch_retries
                    repairs.append(repair)
                    print(
                        f"[{args.city}] repair_downloaded catalog_id={target.catalog_id} "
                        f"path={repair['path']} size={repair['size']} method={repair['method']} "
                        f"fetch_retries={fetch_retries}",
                        flush=True,
                    )
                    if len(repairs) >= args.apply_batch_size:
                        _flush_repairs()
                except Exception as exc:
                    reason = _failure_reason(exc)
                    failure_counts[reason] += 1
                    if reason == "generated_pdf_html_retryable":
                        generated_pdf_retry_stats["generated_pdf_html_retryable"] += 1
                    if reason in {"remote_disconnected", "incomplete_read", "connection_error", "read_timeout"}:
                        generated_pdf_retry_stats["generated_pdf_transport_retryable"] += 1
                    if reason == "invalid_partial_pdf":
                        generated_pdf_retry_stats["generated_pdf_invalid_partial_pdf"] += 1
                    if collect_retryables and reason in RETRYABLE_FAILURE_REASONS:
                        retry_targets.append(target)
                    else:
                        failed += 1
                    print(
                        f"[{args.city}] repair_failed catalog_id={target.catalog_id} reason={reason} error={exc}",
                        flush=True,
                    )

    fast_targets = [target for target in classified_targets if target.preferred_method == "electronic_file"]
    generated_targets = [target for target in classified_targets if target.preferred_method == "generated_pdf"]

    if args.retry_only:
        retry_targets = classified_targets
    else:
        _run_lane(
            "fast",
            fast_targets,
            workers=args.workers,
            force_generated_pdf=False,
            collect_retryables=True,
            pdf_transition_timeout_seconds=args.pdf_transition_timeout,
        )
        _run_lane(
            "generated_pdf",
            generated_targets,
            workers=args.generated_pdf_workers,
            force_generated_pdf=True,
            collect_retryables=True,
            pdf_transition_timeout_seconds=args.pdf_transition_timeout,
        )
    _run_lane(
        "retry",
        retry_targets,
        workers=args.generated_pdf_workers,
        force_generated_pdf=True,
        collect_retryables=False,
        pdf_transition_timeout_seconds=max(args.pdf_transition_timeout, PDF_TRANSITION_TIMEOUT_SECONDS * 2),
    )

    _flush_repairs()
    failure_summary = dict(sorted(failure_counts.items()))
    retrieval_summary = dict(sorted(retrieval_counts.items()))
    retry_summary = dict(sorted(generated_pdf_retry_stats.items()))
    last_catalog_id = max((target.catalog_id for target in classified_targets), default=args.resume_after_id)
    print(
        f"[{args.city}] repair_finish downloaded={len(targets) - failed} failed={failed} "
        f"updated={total_updated} skipped_duplicate_hash={total_skipped_duplicate_hash} "
        f"retrieval_counts={retrieval_summary} failure_counts={failure_summary} "
        f"retry_stats={retry_summary} "
        f"resume_after_id={last_catalog_id}",
        flush=True,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
