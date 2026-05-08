from typing import Any, Callable

from pipeline.summary_backfill_dispatch import enqueue_embed_catalogs as _enqueue_embed_catalogs
from pipeline.summary_backfill_queries import (
    select_catalog_ids_for_summary_hydration,
    summary_doc_kind_map as _summary_doc_kind_map,
    summary_doc_kind_subquery as _summary_doc_kind_subquery,
)
from pipeline.summary_backfill_runner import run_summary_hydration_backfill as _run_summary_hydration_backfill_impl


def run_summary_hydration_backfill(
    force: bool = False,
    limit: int | None = None,
    city: str | None = None,
    *,
    summary_timeout_seconds: int | None = None,
    summary_fallback_mode: str = "none",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_every: int = 25,
    generate_summary_callable: Callable[[int], dict[str, Any]],
    agenda_embed_callback: Callable[[list[int]], dict[str, object]] | None = None,
    session_factory: Callable[[], Any] | None = None,
    select_catalog_ids_callable: Callable[[Any, int | None, str | None], list[int]] | None = None,
    summary_doc_kind_map_callable: Callable[[Any, list[int]], dict[int, str]] | None = None,
    agenda_summary_batch_builder: Callable[..., dict[str, Any]] | None = None,
    summarize_catalog_callable: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, int]:
    # Resolve embed dispatch through this facade so existing monkeypatch seams stay live.
    return _run_summary_hydration_backfill_impl(
        force=force,
        limit=limit,
        city=city,
        summary_timeout_seconds=summary_timeout_seconds,
        summary_fallback_mode=summary_fallback_mode,
        progress_callback=progress_callback,
        progress_every=progress_every,
        generate_summary_callable=generate_summary_callable,
        agenda_embed_callback=agenda_embed_callback or _enqueue_embed_catalogs,
        **({"session_factory": session_factory} if session_factory is not None else {}),
        **(
            {"select_catalog_ids_callable": select_catalog_ids_callable}
            if select_catalog_ids_callable is not None
            else {}
        ),
        **(
            {"summary_doc_kind_map_callable": summary_doc_kind_map_callable}
            if summary_doc_kind_map_callable is not None
            else {}
        ),
        **(
            {"agenda_summary_batch_builder": agenda_summary_batch_builder}
            if agenda_summary_batch_builder is not None
            else {}
        ),
        **(
            {"summarize_catalog_callable": summarize_catalog_callable} if summarize_catalog_callable is not None else {}
        ),
    )


__all__ = [
    "_enqueue_embed_catalogs",
    "_summary_doc_kind_map",
    "_summary_doc_kind_subquery",
    "run_summary_hydration_backfill",
    "select_catalog_ids_for_summary_hydration",
]
