from datetime import datetime, timezone
import logging

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Catalog, AgendaItem, Document
from pipeline.db_session import db_session
from pipeline.config import AGENDA_BATCH_SIZE
from pipeline.laserfiche_error_pages import catalog_has_laserfiche_error_content
from pipeline.llm import LocalAI
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import resolve_agenda_items


logger = logging.getLogger("agenda-worker")


def select_catalog_ids_for_agenda_segmentation(session, limit: int | None = None) -> list[int]:
    """
    Return hydrated agenda catalogs that still need segmentation work.

    Empty terminal states are intentionally excluded so batch backfills do not
    churn forever on catalogs that produced no substantive agenda items.
    """
    query = (
        session.query(Catalog.id)
        .join(Document, Catalog.id == Document.catalog_id)
        .outerjoin(AgendaItem, Catalog.id == AgendaItem.catalog_id)
        .filter(
            Document.category == "agenda",
            Catalog.content != None,
            Catalog.content != "",
            or_(
                Catalog.agenda_segmentation_status == None,
                Catalog.agenda_segmentation_status == "failed",
                and_(
                    Catalog.agenda_segmentation_status == "complete",
                    AgendaItem.page_number == None,
                ),
            ),
        )
        .distinct()
        .order_by(Catalog.id)
    )
    if limit is not None:
        query = query.limit(limit)
    return [row[0] for row in query.all()]

def segment_document_agenda(catalog_id):
    """
    Intelligence Worker: Uses Local AI (Gemma 3) to split a single document
    into individual, searchable 'Agenda Items'.

    What this does:
    1. Reads a meeting document (PDF or HTML)
    2. Uses the local AI model to identify individual agenda items
    3. Extracts each item's title, description, and page number
    4. Saves each item as a separate database record for targeted search

    Why segment agendas?
    A typical city council meeting has 10-20 different topics discussed.
    By splitting them into separate items, users can search for and link to
    specific topics like "Bike Lane Proposal" instead of the entire 200-page packet.

    What the AI looks for:
    - Item numbers ("Item 1", "5.1", "A.")
    - Bold section headers
    - Page transitions that indicate new topics
    - Patterns like "MOVED BY" and "SECONDED BY" that indicate actions
    """
    # Use context manager for automatic session cleanup and error handling
    with db_session() as session:
        try:
            catalog = session.get(Catalog, catalog_id)
            if not catalog or not catalog.content:
                return
            if catalog_has_laserfiche_error_content(catalog):
                catalog.agenda_segmentation_status = "failed"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = "laserfiche_error_page_detected"
                session.commit()
                return
            local_ai = LocalAI()

            # Find the associated document to get the event_id
            # We need this to link agenda items to specific meetings
            doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
            if not doc or not doc.event_id:
                return

            resolved = resolve_agenda_items(session, catalog, doc, local_ai)
            items_data = resolved["items"]
            logger.info(
                "agenda_segmentation_resolved catalog_id=%s source_used=%s quality_score=%s llm_fallback_invoked=%s raw_legistar_count=%s filtered_legistar_count=%s legistar_accepted=%s",
                catalog.id,
                resolved.get("source_used"),
                resolved.get("quality_score"),
                resolved.get("llm_fallback_invoked", False),
                resolved.get("raw_legistar_count"),
                resolved.get("filtered_legistar_count"),
                resolved.get("legistar_accepted"),
            )

            if items_data:
                # Rebuild rows so reruns remain idempotent and source quality can improve.
                persist_agenda_items(session, catalog.id, doc.event_id, items_data)
                catalog.agenda_segmentation_status = "complete"
                catalog.agenda_segmentation_item_count = len(items_data)
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = None
            else:
                # Terminal empty state: don't reprocess forever.
                catalog.agenda_segmentation_status = "empty"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = None

            # Save all items (or empty/failed status) at once.
            session.commit()
        except SQLAlchemyError as e:
            # Database errors during agenda segmentation: What can fail?
            # - IntegrityError: Duplicate agenda items (race condition with another worker)
            # - DataError: AI extracted content that's too large for database fields
            # - OperationalError: Database connection lost during AI processing
            # Why is AI processing mentioned? extract_agenda() can take 10-30 seconds,
            # plenty of time for connections to timeout or other issues to occur.
            # Note: The context manager (db_session) automatically rolls back on exception
            try:
                catalog = session.get(Catalog, catalog_id)
                if catalog:
                    catalog.agenda_segmentation_status = "failed"
                    catalog.agenda_segmentation_item_count = 0
                    catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                    catalog.agenda_segmentation_error = str(e)[:500]
                    session.commit()
            except Exception:
                # The context manager will rollback; keep legacy print for visibility.
                pass
            print(f"Error segmenting {catalog_id}: {e}")
            # The context manager will automatically rollback on exception

def segment_agendas():
    """
    Legacy batch processing function.

    What this does:
    1. Finds documents that need agenda extraction (haven't been processed yet)
    2. Processes them in small batches to avoid overwhelming the AI model
    3. Each document gets split into individual agenda items

    Why batch processing?
    The local AI model uses RAM and CPU. Processing too many at once could
    cause memory issues. Small batches provide faster feedback and are easier
    to monitor.

    What documents get processed?
    - Documents with content (not empty)
    - Documents without agenda items OR with incomplete items (no page numbers)
    - Limited to a batch size to keep processing times reasonable
    """
    # Use context manager for automatic session cleanup
    with db_session() as session:
        ids = select_catalog_ids_for_agenda_segmentation(session, limit=AGENDA_BATCH_SIZE)

    # Process each document (each will create its own session)
    for cid in ids:
        segment_document_agenda(cid)


def run_agenda_segmentation_backfill(limit: int | None = None) -> dict[str, int]:
    """
    Run agenda segmentation once across the currently eligible backlog.

    We snapshot the backlog up front so failed rows are not retried repeatedly
    within the same pipeline run.
    """
    with db_session() as session:
        catalog_ids = select_catalog_ids_for_agenda_segmentation(session, limit=limit)

    counts = {
        "selected": len(catalog_ids),
        "complete": 0,
        "empty": 0,
        "failed": 0,
        "other": 0,
    }
    if not catalog_ids:
        logger.info("agenda_segmentation_backfill selected=0")
        return counts

    for cid in catalog_ids:
        segment_document_agenda(cid)
        with db_session() as session:
            catalog = session.get(Catalog, cid)
            status = getattr(catalog, "agenda_segmentation_status", None) if catalog else None
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1

    logger.info(
        "agenda_segmentation_backfill selected=%s complete=%s empty=%s failed=%s other=%s",
        counts["selected"],
        counts["complete"],
        counts["empty"],
        counts["failed"],
        counts["other"],
    )
    return counts

if __name__ == "__main__":
    segment_agendas()
