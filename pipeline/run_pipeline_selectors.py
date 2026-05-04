import logging
from typing import TypeAlias

from sqlalchemy import Text, cast, or_

from pipeline.profiling import apply_catalog_id_scope
from pipeline.run_pipeline_onboarding import OnboardingScopeConfig, scope_catalog_query_for_onboarding


CATALOG_SELECTOR_BATCH_SIZE = 1000
FAILED_TERMINAL_EXTRACTION_STATUS = "failed_terminal"

SqlExpression: TypeAlias = object


def catalog_entities_need_nlp(catalog_model: object) -> SqlExpression:
    # Postgres `json` columns do not support equality, so JSON null checks must
    # compare the serialized value instead of using `= 'null'`.
    return or_(
        catalog_model.entities.is_(None),
        cast(catalog_model.entities, Text) == "null",
        catalog_model.content_hash.is_(None),
        catalog_model.entities_source_hash.is_(None),
        catalog_model.entities_source_hash != catalog_model.content_hash,
    )


def _extraction_catalog_query(db: object) -> object:
    from pipeline.models import Catalog

    return db.query(Catalog.id).filter(
        Catalog.content.is_(None),
        (Catalog.extraction_status.is_(None)) | (Catalog.extraction_status != FAILED_TERMINAL_EXTRACTION_STATUS),
    )


def _terminal_extraction_failure_count(db: object) -> int:
    from pipeline.models import Catalog

    return (
        db.query(Catalog.id)
        .filter(Catalog.content.is_(None), Catalog.extraction_status == FAILED_TERMINAL_EXTRACTION_STATUS)
        .count()
    )


def _log_processing_selection(
    *,
    logger: logging.Logger,
    onboarding_config: OnboardingScopeConfig,
    extraction_count: int,
    terminal_failure_count: int,
) -> None:
    if onboarding_config.city:
        logger.info(
            "onboarding_scope city=%s selected_missing_work_catalogs=%s extraction_needed=%s excluded_terminal_failures=%s",
            onboarding_config.city,
            extraction_count,
            extraction_count,
            terminal_failure_count,
        )
        return
    logger.info(
        "global_scope selected_missing_work_catalogs=%s extraction_needed=%s excluded_terminal_failures=%s",
        extraction_count,
        extraction_count,
        terminal_failure_count,
    )


def select_catalog_ids_for_processing(
    db: object,
    *,
    onboarding_config: OnboardingScopeConfig,
    logger: logging.Logger,
) -> list[int]:
    from pipeline.models import Catalog

    extraction_query = _extraction_catalog_query(db)
    extraction_query = apply_catalog_id_scope(extraction_query, Catalog.id)
    extraction_query, _touched_hash_count = scope_catalog_query_for_onboarding(
        db,
        extraction_query,
        config=onboarding_config,
        logger=logger,
    )

    extraction_ids = [row[0] for row in extraction_query.yield_per(CATALOG_SELECTOR_BATCH_SIZE)]
    _log_processing_selection(
        logger=logger,
        onboarding_config=onboarding_config,
        extraction_count=len(extraction_ids),
        terminal_failure_count=_terminal_extraction_failure_count(db),
    )
    return extraction_ids


def select_catalog_ids_for_entity_backfill(
    db: object,
    *,
    onboarding_config: OnboardingScopeConfig,
    logger: logging.Logger,
) -> list[int]:
    from pipeline.models import Catalog

    query = db.query(Catalog.id).filter(
        Catalog.content.isnot(None),
        Catalog.content != "",
        catalog_entities_need_nlp(Catalog),
    )
    query = apply_catalog_id_scope(query, Catalog.id)
    query, _touched_hash_count = scope_catalog_query_for_onboarding(
        db,
        query,
        config=onboarding_config,
        logger=logger,
    )
    return [row[0] for row in query.yield_per(CATALOG_SELECTOR_BATCH_SIZE)]
