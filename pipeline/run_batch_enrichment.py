import argparse
import logging
import sys

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
    run_step("Entity Backfill", ["python", "backfill_entities.py"])
    run_step("Table Extraction", ["python", "table_worker.py"])
    run_step("Backfill Organizations", ["python", "backfill_orgs.py"])
    run_step("Topic Modeling", ["python", "topic_worker.py"])
    run_step("People Linking", ["python", "person_linker.py"])
    run_step("Search Indexing", ["python", "indexer.py"])
    logger.info("<<< Batch Enrichment Pipeline Complete")


if __name__ == "__main__":
    main(sys.argv[1:])
