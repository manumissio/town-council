from collections.abc import Mapping
from typing import Any, Callable

from pipeline.summary_backfill import (
    _enqueue_embed_catalogs as _enqueue_embed_catalogs_impl,
    _summary_doc_kind_map as _summary_doc_kind_map_impl,
    _summary_doc_kind_subquery as _summary_doc_kind_subquery_impl,
    run_summary_hydration_backfill as run_summary_hydration_backfill_impl,
    select_catalog_ids_for_summary_hydration as select_catalog_ids_for_summary_hydration_impl,
)
from pipeline.task_agenda_segmentation import (
    AgendaSegmentationTaskServices,
    persist_agenda_segmentation_failure_status as persist_agenda_segmentation_failure_status_impl,
    record_agenda_segmentation_status as record_agenda_segmentation_status_impl,
    run_post_segmentation_vote_extraction as run_post_segmentation_vote_extraction_impl,
    run_segment_agenda_task_family as run_segment_agenda_task_family_impl,
)
from pipeline.task_text_extraction import run_extract_text_task_family as run_extract_text_task_family_impl
from pipeline.task_vote_extraction import run_extract_votes_task_family as run_extract_votes_task_family_impl


def _summary_doc_kind_subquery(db: Any) -> Any:
    return _summary_doc_kind_subquery_impl(db)


def select_catalog_ids_for_summary_hydration(db: Any, limit: int | None = None, city: str | None = None) -> list[int]:
    return select_catalog_ids_for_summary_hydration_impl(db, limit=limit, city=city)


def _summary_doc_kind_map(db: Any, catalog_ids: list[int]) -> dict[int, str]:
    return _summary_doc_kind_map_impl(db, catalog_ids)


def _enqueue_embed_catalogs(catalog_ids: list[int]) -> dict[str, object]:
    return _enqueue_embed_catalogs_impl(catalog_ids)


def run_summary_hydration_backfill(
    facade: Mapping[str, Any],
    *,
    force: bool,
    limit: int | None,
    city: str | None,
    summary_timeout_seconds: int | None,
    summary_fallback_mode: str,
    progress_callback: Callable[[dict[str, Any]], None] | None,
    progress_every: int,
) -> dict[str, int]:
    return run_summary_hydration_backfill_impl(
        force=force,
        limit=limit,
        city=city,
        summary_timeout_seconds=summary_timeout_seconds,
        summary_fallback_mode=summary_fallback_mode,
        progress_callback=progress_callback,
        progress_every=progress_every,
        generate_summary_callable=lambda catalog_id: facade["generate_summary_task"].run(catalog_id, force=force),
        session_factory=facade["SessionLocal"],
        select_catalog_ids_callable=facade["select_catalog_ids_for_summary_hydration"],
        summary_doc_kind_map_callable=facade["_summary_doc_kind_map"],
        agenda_summary_batch_builder=facade["build_deterministic_agenda_summary_payloads"],
        non_agenda_summary_builder=facade["build_deterministic_non_agenda_summary_payload"],
        summarize_catalog_callable=facade["summarize_catalog_with_maintenance_mode"],
    )


def run_extract_text_task_family(
    facade: Mapping[str, Any],
    db: Any,
    catalog_id: int,
    *,
    force: bool,
    ocr_fallback: bool,
) -> dict[str, Any]:
    return run_extract_text_task_family_impl(
        db,
        catalog_id,
        force=force,
        ocr_fallback=ocr_fallback,
        min_chars=facade["TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR"],
        reextract_catalog_content_callable=facade["reextract_catalog_content"],
        reindex_catalog_callable=facade["reindex_catalog"],
    )


def run_extract_votes_task_family(
    facade: Mapping[str, Any],
    db: Any,
    catalog_id: int,
    *,
    force: bool,
    local_ai: Any,
) -> dict[str, Any]:
    return run_extract_votes_task_family_impl(
        db,
        catalog_id,
        force=force,
        local_ai=local_ai,
        vote_extraction_enabled=facade["ENABLE_VOTE_EXTRACTION"],
        run_vote_extraction_for_catalog_callable=facade["run_vote_extraction_for_catalog"],
        reindex_catalog_callable=facade["reindex_catalog"],
    )


def agenda_segmentation_task_services(facade: Mapping[str, Any]) -> AgendaSegmentationTaskServices:
    return AgendaSegmentationTaskServices(
        classify_catalog_bad_content=facade["classify_catalog_bad_content"],
        has_viable_structured_agenda_source=facade["has_viable_structured_agenda_source"],
        resolve_agenda_items=facade["resolve_agenda_items"],
        persist_agenda_items=facade["persist_agenda_items"],
        run_vote_extraction_for_catalog=facade["run_vote_extraction_for_catalog"],
        reindex_catalog=facade["reindex_catalog"],
        vote_extraction_enabled=facade["ENABLE_VOTE_EXTRACTION"],
    )


def record_agenda_segmentation_status(
    catalog: Any,
    *,
    status: str,
    item_count: int,
    error_message: str | None,
) -> None:
    record_agenda_segmentation_status_impl(
        catalog,
        status=status,
        item_count=item_count,
        error_message=error_message,
    )


def run_post_segmentation_vote_extraction(
    facade: Mapping[str, Any],
    db: Any,
    *,
    local_ai: Any,
    catalog: Any,
    doc: Any,
    created_items: list[Any],
) -> dict[str, Any]:
    return run_post_segmentation_vote_extraction_impl(
        db,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        created_items=created_items,
        services=agenda_segmentation_task_services(facade),
    )


def persist_agenda_segmentation_failure_status(db: Any, catalog_id: int, error_message: str) -> None:
    persist_agenda_segmentation_failure_status_impl(db, catalog_id, error_message)


def run_segment_agenda_task_family(
    facade: Mapping[str, Any],
    db: Any,
    catalog_id: int,
    *,
    local_ai: Any,
) -> dict[str, Any]:
    return run_segment_agenda_task_family_impl(
        db,
        catalog_id,
        local_ai=local_ai,
        services=agenda_segmentation_task_services(facade),
    )
