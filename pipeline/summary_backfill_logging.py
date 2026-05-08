from pipeline.backlog_maintenance import (
    AGENDA_SUMMARY_BUNDLE_BUILD_MS,
    AGENDA_SUMMARY_EMBED_DISPATCH_MS,
    AGENDA_SUMMARY_PERSIST_MS,
    AGENDA_SUMMARY_REINDEX_MS,
    AGENDA_SUMMARY_RENDER_MS,
)
from pipeline.task_runtime import logger


def log_backfill_counts(counts: dict[str, int]) -> None:
    logger.info(
        "summary_hydration_backfill selected=%s complete=%s changed_catalogs=%s cached=%s stale=%s blocked_low_signal=%s blocked_ungrounded=%s not_generated_yet=%s error=%s other=%s agenda_deterministic_complete=%s llm_complete=%s deterministic_fallback_complete=%s reindexed=%s reindex_failed=%s embed_enqueued=%s embed_dispatch_failed=%s agenda_summary_bundle_build_ms=%s agenda_summary_render_ms=%s agenda_summary_persist_ms=%s agenda_summary_reindex_ms=%s agenda_summary_embed_dispatch_ms=%s",
        counts["selected"],
        counts["complete"],
        counts["changed_catalogs"],
        counts["cached"],
        counts["stale"],
        counts["blocked_low_signal"],
        counts["blocked_ungrounded"],
        counts["not_generated_yet"],
        counts["error"],
        counts["other"],
        counts["agenda_deterministic_complete"],
        counts["llm_complete"],
        counts["deterministic_fallback_complete"],
        counts["reindexed"],
        counts["reindex_failed"],
        counts["embed_enqueued"],
        counts["embed_dispatch_failed"],
        counts[AGENDA_SUMMARY_BUNDLE_BUILD_MS],
        counts[AGENDA_SUMMARY_RENDER_MS],
        counts[AGENDA_SUMMARY_PERSIST_MS],
        counts[AGENDA_SUMMARY_REINDEX_MS],
        counts[AGENDA_SUMMARY_EMBED_DISPATCH_MS],
    )
