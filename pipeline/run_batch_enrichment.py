import argparse
import logging
import sys
import time

from pipeline.db_session import db_session
from pipeline.metrics import record_pipeline_phase_duration
from pipeline.profiling import current_mode, profile_span
from pipeline.run_pipeline import run_callable_step, run_step
from pipeline.backfill_entities import run_entity_backfill
from pipeline.backfill_orgs import run_organization_backfill
from pipeline.person_linker import run_people_linking
from pipeline.table_worker import select_catalog_ids_for_table_extraction
from pipeline.topic_worker import run_topic_hydration_backfill, select_catalog_ids_for_topic_hydration


LOGGER_NAME = "pipeline-batch"
LOGGER_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the CLI edge so imports stay side-effect free."""
    logging.basicConfig(level=logging.INFO, format=LOGGER_FORMAT)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the batch-only enrichment steps after the core pipeline has completed."
    )
    return parser.parse_args(argv)


def run_batch_callable_step(name, phase, func):
    logger.info("Step: %s", name)
    with profile_span(phase=phase, component="pipeline-batch"):
        start_perf = time.perf_counter()
        try:
            result = func()
        except Exception:
            logger.exception("Step %s failed.", name)
            record_pipeline_phase_duration(
                phase,
                "pipeline-batch",
                current_mode(),
                "failure",
                time.perf_counter() - start_perf,
            )
            sys.exit(1)
        duration_s = time.perf_counter() - start_perf
        record_pipeline_phase_duration(
            phase,
            "pipeline-batch",
            current_mode(),
            "success",
            duration_s,
        )
        return result


def main(argv=None):
    _configure_cli_logging()
    parse_args([] if argv is None else argv)
    logger.info(">>> Starting Batch Enrichment Pipeline")
    started = time.perf_counter()
    with profile_span(phase="batch_enrichment_total", component="pipeline-batch"):
        entity_counts = run_callable_step("Entity Backfill", run_entity_backfill, component="pipeline-batch")
        with db_session() as session:
            table_catalog_ids = select_catalog_ids_for_table_extraction(session)
        logger.info("table_extraction_preflight selected=%s", len(table_catalog_ids))
        if table_catalog_ids:
            run_step("Table Extraction", ["python", "table_worker.py"])
        else:
            logger.info("Step: Table Extraction skipped=1 reason=no_eligible_catalogs")
        run_callable_step(
            "Backfill Organizations",
            run_organization_backfill,
            component="pipeline-batch",
        )
        with db_session() as session:
            topic_catalog_ids = select_catalog_ids_for_topic_hydration(session)
        logger.info("topic_modeling_preflight selected=%s", len(topic_catalog_ids))
        if topic_catalog_ids:
            run_batch_callable_step(
                "Topic Modeling",
                "topic_modeling",
                lambda: run_topic_hydration_backfill(catalog_ids=topic_catalog_ids),
            )
        else:
            logger.info("Step: Topic Modeling skipped=1 reason=no_eligible_catalogs")
        changed_catalog_ids = list(entity_counts.get("updated_catalog_ids", [])) if isinstance(entity_counts, dict) else []
        logger.info("people_linking_preflight selected=%s", len(changed_catalog_ids))
        if changed_catalog_ids:
            run_batch_callable_step(
                "People Linking",
                "people_linking",
                lambda: run_people_linking(catalog_ids=changed_catalog_ids),
            )
        else:
            logger.info("Step: People Linking skipped=1 reason=no_changed_entity_catalogs")
    record_pipeline_phase_duration(
        "batch_enrichment_total",
        "pipeline-batch",
        current_mode(),
        "success",
        time.perf_counter() - started,
    )
    logger.info("<<< Batch Enrichment Pipeline Complete")


if __name__ == "__main__":
    main(sys.argv[1:])
