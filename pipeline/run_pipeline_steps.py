import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from typing import TypeVar

from pipeline.metrics import record_pipeline_phase_duration
from pipeline.profiling import profile_span


PIPELINE_PROFILE_MODE_ENV = "TC_PROFILE_MODE"
DEFAULT_PROFILE_MODE = "triage"

STEP_PHASE_NAMES = {
    "DB Migrate": "db_migrate",
    "Seed Places": "seed_places",
    "Promote Staged Events": "promote_stage",
    "Downloader": "download",
    "Agenda Segmentation": "segment_agenda",
    "Summary Hydration": "summarize",
    "Search Indexing": "index_search",
    "Entity Backfill": "entity_backfill",
    "Table Extraction": "table_extraction",
    "Backfill Organizations": "org_backfill",
    "Topic Modeling": "topic_modeling",
    "People Linking": "people_linking",
}

SUBPROCESS_COMPONENT = "subprocess"
STEP_SUCCESS_OUTCOME = "success"
STEP_FAILURE_OUTCOME = "failure"

StepReturn = TypeVar("StepReturn")


def phase_name_for_step(step_name: str) -> str:
    return STEP_PHASE_NAMES.get(step_name, step_name.lower().replace(" ", "_"))


def current_profile_mode() -> str:
    return str(os.getenv(PIPELINE_PROFILE_MODE_ENV, DEFAULT_PROFILE_MODE) or DEFAULT_PROFILE_MODE)


def run_step(
    name: str,
    command: Sequence[str],
    *,
    logger: logging.Logger,
    subprocess_module: object = subprocess,
) -> None:
    logger.info("Step: %s", name)
    phase = phase_name_for_step(name)
    with profile_span(
        phase=phase,
        component=SUBPROCESS_COMPONENT,
        metadata={"command": list(command)},
    ):
        start_perf = time.perf_counter()
        try:
            subprocess_module.run(command, check=True)  # type: ignore[attr-defined]
        except subprocess.CalledProcessError:
            logger.error("Step %s failed.", name)
            record_pipeline_phase_duration(
                phase,
                SUBPROCESS_COMPONENT,
                current_profile_mode(),
                STEP_FAILURE_OUTCOME,
                time.perf_counter() - start_perf,
            )
            sys.exit(1)
        record_pipeline_phase_duration(
            phase,
            SUBPROCESS_COMPONENT,
            current_profile_mode(),
            STEP_SUCCESS_OUTCOME,
            time.perf_counter() - start_perf,
        )


def run_callable_step(
    name: str,
    func: Callable[[], StepReturn],
    *,
    logger: logging.Logger,
    component: str = "pipeline",
) -> StepReturn:
    logger.info("Step: %s", name)
    phase = phase_name_for_step(name)
    with profile_span(phase=phase, component=component):
        start_perf = time.perf_counter()
        try:
            step_result = func()
        except Exception:
            logger.error("Step %s failed.", name)
            record_pipeline_phase_duration(
                phase,
                component,
                current_profile_mode(),
                STEP_FAILURE_OUTCOME,
                time.perf_counter() - start_perf,
            )
            sys.exit(1)
        record_pipeline_phase_duration(
            phase,
            component,
            current_profile_mode(),
            STEP_SUCCESS_OUTCOME,
            time.perf_counter() - start_perf,
        )
        return step_result
