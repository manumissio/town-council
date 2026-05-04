from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import logging
from multiprocessing import cpu_count
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

from pipeline.config import (
    AGENDA_SEGMENT_MAINTENANCE_TIMEOUT_SECONDS,
    DB_RETRY_DELAY_MAX,
    DB_RETRY_DELAY_MIN,
    DOCUMENT_CHUNK_SIZE,
    MAX_WORKERS,
    PIPELINE_CPU_FRACTION,
    PIPELINE_ONBOARDING_CITY,
    PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE,
    PIPELINE_ONBOARDING_MAX_WORKERS,
    PIPELINE_ONBOARDING_STARTED_AT_UTC,
    PIPELINE_RUNTIME_PROFILE,
    SUMMARY_HYDRATION_MAINTENANCE_TIMEOUT_SECONDS,
    TIKA_OCR_FALLBACK_ENABLED,
)
from pipeline.profiling import profile_span, workload_only_profile
from pipeline.run_pipeline_extraction import process_document_chunk as _process_document_chunk_impl
from pipeline.run_pipeline_onboarding import OnboardingScopeConfig
from pipeline.run_pipeline_parallel import (
    ParallelProcessingDependencies,
    ParallelProcessingRuntime,
    resolve_parallel_processing_settings,
    run_parallel_processing as _run_parallel_processing_impl,
)
from pipeline.run_pipeline_selectors import (
    catalog_entities_need_nlp as _catalog_entities_need_nlp_impl,
    select_catalog_ids_for_entity_backfill as _select_catalog_ids_for_entity_backfill_impl,
    select_catalog_ids_for_processing as _select_catalog_ids_for_processing_impl,
)
from pipeline.run_pipeline_steps import (
    current_profile_mode as _current_profile_mode_impl,
    phase_name_for_step as _phase_name_for_step_impl,
    run_callable_step as _run_callable_step_impl,
    run_step as _run_step_impl,
)
from pipeline.startup_purge import run_startup_purge_if_enabled


LOGGER_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
PIPELINE_LOGGER_NAME = "pipeline-manager"
PIPELINE_COMPONENT = "pipeline"
PYTHON_COMMAND = "python"
WORKLOAD_ONLY_PRELUDE_STEPS = "db_migrate,seed_places,promote_stage,downloader"
ONBOARDING_FAST_PROFILE = "onboarding_fast"

logging.basicConfig(level=logging.INFO, format=LOGGER_FORMAT)
logger = logging.getLogger(PIPELINE_LOGGER_NAME)

__all__ = (
    "AGENDA_SEGMENT_MAINTENANCE_TIMEOUT_SECONDS",
    "DB_RETRY_DELAY_MAX",
    "DB_RETRY_DELAY_MIN",
    "DOCUMENT_CHUNK_SIZE",
    "MAX_WORKERS",
    "PIPELINE_CPU_FRACTION",
    "PIPELINE_ONBOARDING_CITY",
    "PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE",
    "PIPELINE_ONBOARDING_MAX_WORKERS",
    "PIPELINE_ONBOARDING_STARTED_AT_UTC",
    "PIPELINE_RUNTIME_PROFILE",
    "ProcessPoolExecutor",
    "SUMMARY_HYDRATION_MAINTENANCE_TIMEOUT_SECONDS",
    "TIKA_OCR_FALLBACK_ENABLED",
    "_catalog_entities_need_nlp",
    "_current_profile_mode",
    "_phase_name_for_step",
    "_resolve_parallel_processing_settings",
    "as_completed",
    "datetime",
    "main",
    "process_document_chunk",
    "run_callable_step",
    "run_parallel_processing",
    "run_step",
    "select_catalog_ids_for_entity_backfill",
    "select_catalog_ids_for_processing",
    "subprocess",
)


def _onboarding_scope_config() -> OnboardingScopeConfig:
    return OnboardingScopeConfig(
        city=PIPELINE_ONBOARDING_CITY,
        started_at_utc=PIPELINE_ONBOARDING_STARTED_AT_UTC,
    )


def _catalog_entities_need_nlp(catalog_model: object) -> object:
    return _catalog_entities_need_nlp_impl(catalog_model)


def select_catalog_ids_for_processing(db: object) -> list[int]:
    return _select_catalog_ids_for_processing_impl(
        db,
        onboarding_config=_onboarding_scope_config(),
        logger=logger,
    )


def select_catalog_ids_for_entity_backfill(db: object) -> list[int]:
    return _select_catalog_ids_for_entity_backfill_impl(
        db,
        onboarding_config=_onboarding_scope_config(),
        logger=logger,
    )


def run_step(name: str, command: Sequence[str]) -> None:
    _run_step_impl(name, command, logger=logger, subprocess_module=subprocess)


def run_callable_step(
    name: str,
    func: Callable[[], Any],
    *,
    component: str = PIPELINE_COMPONENT,
) -> Any:
    return _run_callable_step_impl(name, func, logger=logger, component=component)


def process_document_chunk(catalog_ids: Sequence[int], ocr_fallback_enabled: bool | None = None) -> int:
    return _process_document_chunk_impl(
        catalog_ids,
        ocr_fallback_enabled=ocr_fallback_enabled,
        retry_delay_min=DB_RETRY_DELAY_MIN,
        retry_delay_max=DB_RETRY_DELAY_MAX,
    )


def _resolve_parallel_processing_settings() -> dict[str, object]:
    settings = resolve_parallel_processing_settings(
        document_chunk_size=DOCUMENT_CHUNK_SIZE,
        tika_ocr_fallback_enabled=TIKA_OCR_FALLBACK_ENABLED,
        onboarding_city=PIPELINE_ONBOARDING_CITY,
        onboarding_document_chunk_size=PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE,
        onboarding_max_workers=PIPELINE_ONBOARDING_MAX_WORKERS,
    )
    return {
        "mode": settings.mode,
        "chunk_size": settings.chunk_size,
        "workers_override": settings.workers_override,
        "ocr_fallback_enabled": settings.ocr_fallback_enabled,
    }


def _parallel_processing_runtime() -> ParallelProcessingRuntime:
    return ParallelProcessingRuntime(
        onboarding_city=PIPELINE_ONBOARDING_CITY,
        onboarding_started_at_utc=PIPELINE_ONBOARDING_STARTED_AT_UTC,
        max_workers=MAX_WORKERS,
        cpu_fraction=PIPELINE_CPU_FRACTION,
    )


def _parallel_processing_dependencies() -> ParallelProcessingDependencies:
    from pipeline.db_session import db_session

    return ParallelProcessingDependencies(
        db_session_factory=db_session,
        catalog_selector=select_catalog_ids_for_processing,
        chunk_processor=process_document_chunk,
        executor_factory=ProcessPoolExecutor,
        future_iterator=as_completed,
        cpu_count=cpu_count,
        logger=logger,
    )


def run_parallel_processing() -> None:
    settings = resolve_parallel_processing_settings(
        document_chunk_size=DOCUMENT_CHUNK_SIZE,
        tika_ocr_fallback_enabled=TIKA_OCR_FALLBACK_ENABLED,
        onboarding_city=PIPELINE_ONBOARDING_CITY,
        onboarding_document_chunk_size=PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE,
        onboarding_max_workers=PIPELINE_ONBOARDING_MAX_WORKERS,
    )
    _run_parallel_processing_impl(
        settings=settings,
        runtime=_parallel_processing_runtime(),
        dependencies=_parallel_processing_dependencies(),
    )


def _run_post_processing_steps() -> None:
    logger.info("post_processing_search_indexing skipped=1 mode=targeted_only")


def _run_ingest_prelude_steps() -> None:
    # Profiling selected-manifest runs should measure only the chosen workload,
    # not unrelated global staging activity.
    if workload_only_profile():
        logger.info(
            "profiling_workload_only enabled=1 skipped_prelude=%s",
            WORKLOAD_ONLY_PRELUDE_STEPS,
        )
        return
    run_step("DB Migrate", [PYTHON_COMMAND, "db_migrate.py"])
    run_step("Seed Places", [PYTHON_COMMAND, "seed_places.py"])
    run_step("Promote Staged Events", [PYTHON_COMMAND, "promote_stage.py"])
    run_step("Downloader", [PYTHON_COMMAND, "downloader.py"])


def _run_generation_backfill_steps() -> None:
    from functools import partial

    from pipeline.agenda_worker import run_agenda_segmentation_backfill
    from pipeline.tasks import run_summary_hydration_backfill

    # Agenda summaries depend on structured agenda items, so segmentation must
    # run before summary hydration in the canonical batch pipeline.
    run_callable_step(
        "Agenda Segmentation",
        partial(
            run_agenda_segmentation_backfill,
            segment_mode="maintenance",
            agenda_timeout_seconds=AGENDA_SEGMENT_MAINTENANCE_TIMEOUT_SECONDS,
        ),
    )
    # Reuse the same summary-task rules as the interactive path instead of
    # duplicating prompt, grounding, or caching behavior in the pipeline.
    run_callable_step(
        "Summary Hydration",
        partial(
            run_summary_hydration_backfill,
            summary_timeout_seconds=SUMMARY_HYDRATION_MAINTENANCE_TIMEOUT_SECONDS,
            summary_fallback_mode="deterministic",
        ),
    )


def _should_skip_generation_backfill_steps() -> bool:
    # The onboarding runner already does city-scoped segmentation after the
    # extraction subprocess returns. Skipping the global backfills here keeps
    # first-time onboarding from waking unrelated city backlog.
    return bool(PIPELINE_ONBOARDING_CITY) and PIPELINE_RUNTIME_PROFILE == ONBOARDING_FAST_PROFILE


def main() -> None:
    logger.info(">>> Starting High-Performance Pipeline")
    with profile_span(phase="pipeline_total", component=PIPELINE_COMPONENT):
        purge_result = run_startup_purge_if_enabled()
        logger.info("startup_purge_result=%s", purge_result)

        _run_ingest_prelude_steps()

        logger.info(">>> Starting Parallel Processing (OCR + NLP)")
        run_parallel_processing()

        if _should_skip_generation_backfill_steps():
            logger.info(
                "generation_backfills skipped=1 mode=onboarding_fast city=%s handled_by=city_runner",
                PIPELINE_ONBOARDING_CITY,
            )
        else:
            _run_generation_backfill_steps()

        _run_post_processing_steps()

    logger.info("<<< Pipeline Complete")


def _phase_name_for_step(step_name: str) -> str:
    return _phase_name_for_step_impl(step_name)


def _current_profile_mode() -> str:
    return _current_profile_mode_impl()


if __name__ == "__main__":
    main()
