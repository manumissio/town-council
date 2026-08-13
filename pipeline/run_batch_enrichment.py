import argparse
import logging
import sys
import time

from pipeline.cli_logging import configure_cli_logging
from pipeline.db_session import db_session
from pipeline.metrics import record_pipeline_phase_duration
from pipeline.profiling import (
    append_phase_eligibility,
    current_mode,
    observer_seconds,
    profile_observer,
    profile_span,
    profiling_enabled,
    workload_duration_seconds,
)
from pipeline.run_pipeline import run_callable_step, run_step
from pipeline.backfill_entities import (
    capture_entity_backfill_after_eligibility,
    run_entity_backfill_workload,
)
from pipeline.backfill_orgs import (
    capture_organization_backfill_after_eligibility,
    run_organization_backfill_workload,
)
from pipeline.table_worker import select_catalog_ids_for_table_extraction
from pipeline.topic_worker import run_topic_hydration_backfill, select_catalog_ids_for_topic_hydration


LOGGER_NAME = "pipeline-batch"
LOGGER_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
STEP_FAILURE_EXIT_CODE = 1
NO_ELIGIBLE_CATALOGS_REASON = "no_eligible_catalogs"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the CLI edge so imports stay side-effect free."""
    configure_cli_logging(LOGGER_FORMAT)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the batch-only enrichment steps after the core pipeline has completed."
    )
    return parser.parse_args(argv)


def run_batch_callable_step(name, phase, func):
    logger.info("Step: %s", name)
    with profile_span(phase=phase, component="pipeline-batch"):
        start_perf = time.perf_counter()
        observer_at_start = observer_seconds()
        try:
            result = func()
        except Exception as exc:
            logger.exception("Step %s failed.", name)
            phase_duration_s = workload_duration_seconds(start_perf, observer_at_start)
            record_pipeline_phase_duration(
                phase,
                "pipeline-batch",
                current_mode(),
                "failure",
                phase_duration_s,
            )
            raise SystemExit(STEP_FAILURE_EXIT_CODE) from exc
        duration_s = workload_duration_seconds(start_perf, observer_at_start)
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
    observer_at_start = observer_seconds()
    capture_eligibility = profiling_enabled()
    with profile_span(phase="batch_enrichment_total", component="pipeline-batch"):
        entity_counts = run_callable_step(
            "Entity Backfill",
            run_entity_backfill_workload,
            component="pipeline-batch",
        )
        capture_entity_backfill_after_eligibility(entity_counts)
        with db_session() as session:
            table_catalog_ids = select_catalog_ids_for_table_extraction(session)
        if capture_eligibility:
            append_phase_eligibility(
                phase="table_extraction",
                boundary="before",
                subject="catalog",
                eligible_ids=table_catalog_ids,
            )
        logger.info("table_extraction_preflight selected=%s", len(table_catalog_ids))
        if table_catalog_ids:
            run_step("Table Extraction", ["python", "table_worker.py"])
            if capture_eligibility:
                with profile_observer():
                    with db_session() as session:
                        remaining_table_catalog_ids = select_catalog_ids_for_table_extraction(session)
                    append_phase_eligibility(
                        phase="table_extraction",
                        boundary="after",
                        subject="catalog",
                        eligible_ids=remaining_table_catalog_ids,
                    )
        else:
            with profile_span(
                phase="table_extraction",
                component="pipeline-batch",
                metadata={"skipped": True, "reason": NO_ELIGIBLE_CATALOGS_REASON},
            ):
                logger.info("Step: Table Extraction skipped=1 reason=no_eligible_catalogs")
            if capture_eligibility:
                append_phase_eligibility(
                    phase="table_extraction",
                    boundary="after",
                    subject="catalog",
                    eligible_ids=[],
                )
        run_callable_step(
            "Backfill Organizations",
            run_organization_backfill_workload,
            component="pipeline-batch",
        )
        capture_organization_backfill_after_eligibility()
        with db_session() as session:
            topic_catalog_ids = select_catalog_ids_for_topic_hydration(session)
        if capture_eligibility:
            append_phase_eligibility(
                phase="topic_modeling",
                boundary="before",
                subject="catalog",
                eligible_ids=topic_catalog_ids,
            )
        logger.info("topic_modeling_preflight selected=%s", len(topic_catalog_ids))
        if topic_catalog_ids:
            run_batch_callable_step(
                "Topic Modeling",
                "topic_modeling",
                lambda: run_topic_hydration_backfill(catalog_ids=topic_catalog_ids),
            )
            if capture_eligibility:
                with profile_observer():
                    with db_session() as session:
                        remaining_topic_catalog_ids = select_catalog_ids_for_topic_hydration(session)
                    append_phase_eligibility(
                        phase="topic_modeling",
                        boundary="after",
                        subject="catalog",
                        eligible_ids=remaining_topic_catalog_ids,
                    )
        else:
            with profile_span(
                phase="topic_modeling",
                component="pipeline-batch",
                metadata={"skipped": True, "reason": NO_ELIGIBLE_CATALOGS_REASON},
            ):
                logger.info("Step: Topic Modeling skipped=1 reason=no_eligible_catalogs")
            if capture_eligibility:
                append_phase_eligibility(
                    phase="topic_modeling",
                    boundary="after",
                    subject="catalog",
                    eligible_ids=[],
                )
    record_pipeline_phase_duration(
        "batch_enrichment_total",
        "pipeline-batch",
        current_mode(),
        "success",
        workload_duration_seconds(started, observer_at_start),
    )
    logger.info("<<< Batch Enrichment Pipeline Complete")


if __name__ == "__main__":
    main(sys.argv[1:])
