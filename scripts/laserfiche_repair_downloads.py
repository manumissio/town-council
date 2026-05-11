from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from pipeline.config import DOWNLOAD_TIMEOUT_SECONDS
from scripts.laserfiche_repair_contracts import (
    GENERATED_PDF_FETCH_RETRIES,
    GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS,
    PDF_TRANSITION_POLL_INTERVAL_SECONDS,
    PDF_TRANSITION_TIMEOUT_SECONDS,
    THREAD_STATE,
    RepairNonRetryableError,
    RepairRetryableError,
    RepairTarget,
    coerce_bool,
    electronic_file_url,
    parse_docview_url,
    parse_electronic_file_url,
    target_path,
    url_to_md5,
)
from scripts import laserfiche_repair_generated_pdf as _generated_pdf
from scripts.laserfiche_repair_pdf_io import laserfiche_headers, worker_session, write_validated_pdf_response


def fetch_basic_document_info(session: requests.Session, *, entry_id: int, repo: str) -> dict[str, object]:
    response = session.post(
        "https://portal.laserfiche.com/Portal/DocumentService.aspx/GetBasicDocumentInfo",
        headers=laserfiche_headers(),
        json={"repoName": repo, "entryId": entry_id},
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"Laserfiche basic document info missing for entry {entry_id}")
    return data


def build_page_range(page_count: int) -> str:
    if page_count <= 0:
        raise RepairNonRetryableError("invalid_page_count", "Laserfiche document has no pages to export")
    return f"1 - {page_count}"


def document_supports_electronic_file(info: dict[str, object]) -> bool:
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
            coerced = coerce_bool(info.get(key))
            if coerced is not None:
                return coerced

    for key in ("edocUrl", "electronicFileUrl", "electronicUrl"):
        value = str(info.get(key) or "").strip()
        if value:
            return True

    return False


def classify_target(target: RepairTarget) -> RepairTarget:
    if target.mode == "salvage":
        entry_id, repo = parse_electronic_file_url(target.old_url)
        new_url = target.old_url
    else:
        entry_id, repo = parse_docview_url(target.old_url)
        new_url = electronic_file_url(entry_id, repo)

    info: dict[str, object] = {}
    try:
        info = fetch_basic_document_info(worker_session(), entry_id=entry_id, repo=repo)
    except (requests.RequestException, ValueError, TypeError, KeyError):
        info = {}

    page_count = int(info.get("pageCount") or 0) if info else 0
    preferred_method = "electronic_file"
    if target.mode != "salvage" and not document_supports_electronic_file(info):
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


def classify_targets(targets: list[RepairTarget], *, workers: int) -> list[RepairTarget]:
    if not targets:
        return []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(classify_target, target) for target in targets]
        return [future.result() for future in as_completed(futures)]


def download_generated_pdf(
    session: requests.Session,
    *,
    entry_id: int,
    repo: str,
    page_count: int,
    temp_path: str,
    final_path: str,
    catalog_id: int,
    pdf_transition_timeout_seconds: int = PDF_TRANSITION_TIMEOUT_SECONDS,
    pdf_transition_poll_interval_seconds: int | None = None,
    generated_pdf_fetch_retries: int | None = None,
    generated_pdf_fetch_retry_delay_seconds: int | None = None,
) -> int:
    page_range = build_page_range(page_count).replace(" ", "+")
    generate = session.post(
        f"https://portal.laserfiche.com/Portal/GeneratePDF10.aspx?key={entry_id}&PageRange={page_range}&Watermark=0&repo={repo}",
        headers=laserfiche_headers(),
        data="{}",
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    generate.raise_for_status()
    token = (generate.text.split("\n", 1)[0] or "").strip().replace("\r", "")
    if not token:
        raise ValueError(f"Laserfiche PDF generation token missing for catalog {catalog_id}")

    _wait_for_generated_pdf(
        session,
        token=token,
        catalog_id=catalog_id,
        timeout_seconds=pdf_transition_timeout_seconds,
        request_timeout_seconds=DOWNLOAD_TIMEOUT_SECONDS,
        poll_interval_seconds=(
            PDF_TRANSITION_POLL_INTERVAL_SECONDS
            if pdf_transition_poll_interval_seconds is None
            else pdf_transition_poll_interval_seconds
        ),
    )
    return _fetch_generated_pdf(
        session,
        token=token,
        entry_id=entry_id,
        temp_path=temp_path,
        final_path=final_path,
        catalog_id=catalog_id,
        request_timeout_seconds=DOWNLOAD_TIMEOUT_SECONDS,
        fetch_retries=GENERATED_PDF_FETCH_RETRIES
        if generated_pdf_fetch_retries is None
        else generated_pdf_fetch_retries,
        retry_delay_seconds=(
            GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS
            if generated_pdf_fetch_retry_delay_seconds is None
            else generated_pdf_fetch_retry_delay_seconds
        ),
    )


def _wait_for_generated_pdf(
    session: requests.Session,
    *,
    token: str,
    catalog_id: int,
    timeout_seconds: int,
    request_timeout_seconds: int = DOWNLOAD_TIMEOUT_SECONDS,
    poll_interval_seconds: int | None = None,
) -> None:
    _generated_pdf.wait_for_generated_pdf(
        session,
        token=token,
        catalog_id=catalog_id,
        timeout_seconds=timeout_seconds,
        request_timeout_seconds=request_timeout_seconds,
        poll_interval_seconds=(
            PDF_TRANSITION_POLL_INTERVAL_SECONDS if poll_interval_seconds is None else poll_interval_seconds
        ),
    )


def _fetch_generated_pdf(
    session: requests.Session,
    *,
    token: str,
    entry_id: int,
    temp_path: str,
    final_path: str,
    catalog_id: int,
    request_timeout_seconds: int = DOWNLOAD_TIMEOUT_SECONDS,
    fetch_retries: int | None = None,
    retry_delay_seconds: int | None = None,
) -> int:
    return _generated_pdf.fetch_generated_pdf(
        session,
        token=token,
        entry_id=entry_id,
        temp_path=temp_path,
        final_path=final_path,
        catalog_id=catalog_id,
        request_timeout_seconds=request_timeout_seconds,
        fetch_retries=GENERATED_PDF_FETCH_RETRIES if fetch_retries is None else fetch_retries,
        retry_delay_seconds=GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS
        if retry_delay_seconds is None
        else retry_delay_seconds,
    )


def _classify_fetch_connection_error(exc: requests.exceptions.ConnectionError) -> RepairRetryableError:
    return _generated_pdf.classify_fetch_connection_error(exc)


def download_repaired_pdf(
    target: RepairTarget,
    *,
    pdf_transition_timeout_seconds: int = PDF_TRANSITION_TIMEOUT_SECONDS,
    force_generated_pdf: bool = False,
) -> dict[str, object]:
    if target.entry_id is None or target.repo is None or target.new_url is None:
        target = classify_target(target)

    assert target.entry_id is not None
    assert target.repo is not None
    assert target.new_url is not None
    new_hash = url_to_md5(target.new_url)
    path, filename = target_path(target.location, new_hash)
    temp_path = f"{path}.tmp.{target.catalog_id}"
    setattr(THREAD_STATE, "last_generated_pdf_fetch_retries", 0)

    session = worker_session()
    direct_error: Exception | None = None
    preferred_method = "generated_pdf" if force_generated_pdf else target.preferred_method
    if preferred_method == "electronic_file":
        try:
            response = session.get(target.new_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
            response.raise_for_status()
            size = write_validated_pdf_response(
                response,
                temp_path=temp_path,
                final_path=path,
                catalog_id=target.catalog_id,
            )
            return _repair_payload(target, new_hash, path, filename, size, "electronic_file", "electronic_file")
        except (RepairRetryableError, RepairNonRetryableError, requests.RequestException, ValueError) as exc:
            direct_error = exc

    viewer_url = f"https://portal.laserfiche.com/Portal/DocView.aspx?id={target.entry_id}&repo={target.repo}"
    viewer = session.get(viewer_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    viewer.raise_for_status()
    page_count = int(target.page_count or 0)
    if page_count <= 0:
        info = fetch_basic_document_info(session, entry_id=target.entry_id, repo=target.repo)
        page_count = int(info.get("pageCount") or 0)
    size = download_generated_pdf(
        session,
        entry_id=target.entry_id,
        repo=target.repo,
        page_count=page_count,
        temp_path=temp_path,
        final_path=path,
        catalog_id=target.catalog_id,
        pdf_transition_timeout_seconds=pdf_transition_timeout_seconds,
    )
    method = f"generated_pdf_after_{type(direct_error).__name__}" if direct_error else "generated_pdf"
    payload = _repair_payload(target, new_hash, path, filename, size, method, "generated_pdf")
    payload["fetch_retries"] = int(getattr(THREAD_STATE, "last_generated_pdf_fetch_retries", 0))
    return payload


def _repair_payload(
    target: RepairTarget,
    new_hash: str,
    path: str,
    filename: str,
    size: int,
    method: str,
    retrieval_type: str,
) -> dict[str, object]:
    return {
        "catalog_id": target.catalog_id,
        "new_url": target.new_url,
        "new_hash": new_hash,
        "path": path,
        "filename": filename,
        "size": size,
        "method": method,
        "retrieval_type": retrieval_type,
    }
