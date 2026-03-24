#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import requests
from sqlalchemy import and_
from pipeline.city_scope import source_aliases_for_city
from pipeline.config import DOWNLOAD_TIMEOUT_SECONDS
from pipeline.db_session import db_session
from pipeline.indexer import reindex_catalog
from pipeline.models import AgendaItem, Catalog, Document, Event, SemanticEmbedding


DOCVIEW_RE = re.compile(r"/DocView\.aspx\?id=(?P<entry_id>\d+)&repo=(?P<repo>[^&]+)", re.IGNORECASE)


def _url_to_md5(value: str) -> str:
    return hashlib.md5((value or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RepairTarget:
    catalog_id: int
    old_url: str
    location: str | None
    mode: str = "docview"


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


def _is_valid_pdf_artifact(path: str | None) -> bool:
    if not path or not os.path.exists(path):
        return False
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False
    return _file_has_pdf_signature(path)


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


def _download_repaired_pdf(target: RepairTarget) -> dict[str, object]:
    if target.mode == "salvage":
        new_url = target.old_url
    else:
        entry_id, repo = _parse_docview_url(target.old_url)
        new_url = _electronic_file_url(entry_id, repo)
    new_hash = _url_to_md5(new_url)
    path, filename = _target_path(target.location, new_hash)
    temp_path = f"{path}.tmp.{target.catalog_id}"

    session = requests.Session()
    session.trust_env = False
    response = session.get(new_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/pdf":
        raise ValueError(f"Unexpected content type {content_type!r} for catalog {target.catalog_id}")

    try:
        with open(temp_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)

        size = os.path.getsize(temp_path)
        if size <= 0:
            raise ValueError(f"Downloaded zero-byte PDF for catalog {target.catalog_id}")
        if not _file_has_pdf_signature(temp_path):
            raise ValueError(f"Downloaded invalid PDF bytes for catalog {target.catalog_id}")

        os.replace(temp_path, path)
        return {
            "catalog_id": target.catalog_id,
            "new_url": new_url,
            "new_hash": new_hash,
            "path": path,
            "filename": filename,
            "size": size,
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


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
    parser.add_argument("--apply-batch-size", type=_positive_int, default=200)
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
        f"dry_run={args.dry_run} salvage_bad_electronicfile={args.salvage_bad_electronicfile}",
        flush=True,
    )
    if not targets:
        return 0

    if args.dry_run:
        for target in targets[:5]:
            if target.mode == "salvage":
                new_url = target.old_url
            else:
                entry_id, repo = _parse_docview_url(target.old_url)
                new_url = _electronic_file_url(entry_id, repo)
            print(
                f"[{args.city}] dry_run catalog_id={target.catalog_id} "
                f"old_url={target.old_url} new_url={new_url}",
                flush=True,
            )
        return 0

    repairs: list[dict[str, object]] = []
    failed = 0
    total_updated = 0
    total_skipped_duplicate_hash = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_download_repaired_pdf, target): target for target in targets}
        for future in as_completed(futures):
            target = futures[future]
            try:
                repair = future.result()
                repairs.append(repair)
                print(
                    f"[{args.city}] repair_downloaded catalog_id={target.catalog_id} "
                    f"path={repair['path']} size={repair['size']}",
                    flush=True,
                )
                if len(repairs) >= args.apply_batch_size:
                    counts = _apply_repairs(repairs, reindex=args.reindex)
                    total_updated += counts["updated"]
                    total_skipped_duplicate_hash += counts["skipped_duplicate_hash"]
                    print(
                        f"[{args.city}] repair_batch_applied updated={counts['updated']} "
                        f"skipped_duplicate_hash={counts['skipped_duplicate_hash']}",
                        flush=True,
                    )
                    repairs = []
            except Exception as exc:
                failed += 1
                print(
                    f"[{args.city}] repair_failed catalog_id={target.catalog_id} error={exc}",
                    flush=True,
                )

    counts = _apply_repairs(repairs, reindex=args.reindex)
    total_updated += counts["updated"]
    total_skipped_duplicate_hash += counts["skipped_duplicate_hash"]
    print(
        f"[{args.city}] repair_finish downloaded={len(targets) - failed} failed={failed} "
        f"updated={total_updated} skipped_duplicate_hash={total_skipped_duplicate_hash}",
        flush=True,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
