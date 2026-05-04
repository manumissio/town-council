import random
import sys
import time
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError

from pipeline.extraction_state import mark_extraction_complete, mark_extraction_failure
from pipeline.metrics import record_pipeline_phase_duration
from pipeline.profiling import profile_span
from pipeline.run_pipeline_steps import current_profile_mode


EXTRACT_CHUNK_PHASE = "extract_chunk"
PIPELINE_COMPONENT = "pipeline"
DB_HEALTHCHECK_SQL = "SELECT 1"
DB_CONNECT_ATTEMPTS = 3
EXTRACTION_EMPTY_TEXT_REASON = "Extraction returned empty text"
EXTRACT_SUCCESS_OUTCOME = "success"
EXTRACT_FAILURE_OUTCOME = "failure"


class ChunkProcessingError(RuntimeError):
    def __init__(self, processed_count: int, original_error: SQLAlchemyError) -> None:
        super().__init__(str(original_error))
        self.processed_count = processed_count
        self.original_error = original_error


def _connect_worker_session(retry_delay_min: float, retry_delay_max: float) -> object | None:
    from pipeline.models import db_connect
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    db = None
    for _attempt in range(DB_CONNECT_ATTEMPTS):
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            db = Session()
            db.execute(text(DB_HEALTHCHECK_SQL))
            return db
        except SQLAlchemyError:
            if db:
                db.close()
            time.sleep(random.uniform(retry_delay_min, retry_delay_max))
    return None


def _process_catalog_record(db: object, catalog_id: int, ocr_fallback_enabled: bool | None) -> bool:
    from pipeline.content_hash import compute_content_hash
    from pipeline.extractor import extract_text
    from pipeline.models import Catalog

    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        return False

    if not catalog.content and catalog.location:
        extracted = extract_text(
            catalog.location,
            ocr_fallback_enabled=ocr_fallback_enabled,
        )
        if extracted:
            catalog.content = extracted
            mark_extraction_complete(catalog, compute_content_hash(catalog.content))
        else:
            mark_extraction_failure(catalog, EXTRACTION_EMPTY_TEXT_REASON)
    elif catalog.content and not getattr(catalog, "content_hash", None):
        # Older rows may predate content hashing.
        mark_extraction_complete(catalog, compute_content_hash(catalog.content))
    elif catalog.content:
        catalog.extraction_status = catalog.extraction_status or "complete"
        catalog.extraction_attempt_count = int(catalog.extraction_attempt_count or 0)

    db.commit()
    return True


def _record_chunk_duration(outcome: str, started_at: float) -> None:
    record_pipeline_phase_duration(
        EXTRACT_CHUNK_PHASE,
        PIPELINE_COMPONENT,
        current_profile_mode(),
        outcome,
        time.perf_counter() - started_at,
    )


def _handle_db_connect_failure(span_meta: dict[str, object], catalog_ids: Sequence[int], started_at: float) -> int:
    span_meta["db_connect"] = "failed"
    _record_chunk_duration(EXTRACT_FAILURE_OUTCOME, started_at)
    print(f"Error: Could not connect to database for chunk {list(catalog_ids)[:2]}...", file=sys.stderr)
    return 0


def _process_chunk_records(db: object, catalog_ids: Sequence[int], ocr_fallback_enabled: bool | None) -> int:
    processed_count = 0
    try:
        for catalog_id in catalog_ids:
            if _process_catalog_record(db, int(catalog_id), ocr_fallback_enabled):
                processed_count += 1
    except SQLAlchemyError as error:
        raise ChunkProcessingError(processed_count, error) from error
    return processed_count


def process_document_chunk(
    catalog_ids: Sequence[int],
    *,
    ocr_fallback_enabled: bool | None,
    retry_delay_min: float,
    retry_delay_max: float,
) -> int:
    chunk_catalog_ids = [int(catalog_id) for catalog_id in catalog_ids]
    with profile_span(
        phase=EXTRACT_CHUNK_PHASE,
        component=PIPELINE_COMPONENT,
        metadata={"catalog_count": len(chunk_catalog_ids)},
    ) as span_meta:
        chunk_started = time.perf_counter()
        db = _connect_worker_session(retry_delay_min, retry_delay_max)
        if not db:
            return _handle_db_connect_failure(span_meta, chunk_catalog_ids, chunk_started)

        processed_count = 0
        try:
            processed_count = _process_chunk_records(db, chunk_catalog_ids, ocr_fallback_enabled)
            span_meta["processed_count"] = processed_count
            _record_chunk_duration(EXTRACT_SUCCESS_OUTCOME, chunk_started)
            return processed_count
        except ChunkProcessingError as error:
            db.rollback()
            processed_count = error.processed_count
            span_meta["error"] = error.original_error.__class__.__name__
            _record_chunk_duration(EXTRACT_FAILURE_OUTCOME, chunk_started)
            print(f"Error processing batch: {error.original_error}", file=sys.stderr)
            return processed_count
        finally:
            db.close()
