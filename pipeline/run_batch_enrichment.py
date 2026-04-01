import argparse
import logging
import sys
import time

from pipeline.metrics import record_pipeline_phase_duration
from pipeline.profiling import current_mode, profile_span
from pipeline.run_pipeline import run_step


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pipeline-batch")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the batch-only enrichment steps after the core pipeline has completed."
    )
    return parser.parse_args(argv)


def main(argv=None):
    parse_args([] if argv is None else argv)
    logger.info(">>> Starting Batch Enrichment Pipeline")
    started = time.perf_counter()
    with profile_span(phase="batch_enrichment_total", component="pipeline-batch"):
        run_step("Entity Backfill", ["python", "backfill_entities.py"])
        run_step("Table Extraction", ["python", "table_worker.py"])
        run_step("Backfill Organizations", ["python", "backfill_orgs.py"])
        run_step("Topic Modeling", ["python", "topic_worker.py"])
        run_step("People Linking", ["python", "person_linker.py"])
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
