from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Catalog, AgendaItem, Document
from pipeline.db_session import db_session
from pipeline.config import AGENDA_BATCH_SIZE
from pipeline.llm import LocalAI
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import resolve_agenda_items

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
    local_ai = LocalAI()

    # Use context manager for automatic session cleanup and error handling
    with db_session() as session:
        try:
            catalog = session.get(Catalog, catalog_id)
            if not catalog or not catalog.content:
                return

            # Find the associated document to get the event_id
            # We need this to link agenda items to specific meetings
            doc = session.query(Document).filter_by(catalog_id=catalog.id).first()
            if not doc or not doc.event_id:
                return

            resolved = resolve_agenda_items(session, catalog, doc, local_ai)
            items_data = resolved["items"]

            if items_data:
                # Rebuild rows so reruns remain idempotent and source quality can improve.
                persist_agenda_items(session, catalog.id, doc.event_id, items_data)

                # Save all items at once
                # The context manager will automatically rollback if this fails
                session.commit()
        except SQLAlchemyError as e:
            # Database errors during agenda segmentation: What can fail?
            # - IntegrityError: Duplicate agenda items (race condition with another worker)
            # - DataError: AI extracted content that's too large for database fields
            # - OperationalError: Database connection lost during AI processing
            # Why is AI processing mentioned? extract_agenda() can take 10-30 seconds,
            # plenty of time for connections to timeout or other issues to occur.
            # Note: The context manager (db_session) automatically rolls back on exception
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
        # Complex query to find documents needing agenda extraction:
        # 1. Join with Document table (we need event_id)
        # 2. Left join with AgendaItem (to check if items exist)
        # 3. Filter for documents with content
        # 4. Filter for documents without items OR with incomplete items
        to_process = session.query(Catalog).join(
            Document, Catalog.id == Document.catalog_id
        ).outerjoin(
            AgendaItem, Catalog.id == AgendaItem.catalog_id
        ).filter(
            Catalog.content != None,
            Catalog.content != "",
            or_(
                AgendaItem.id == None,  # No items exist yet
                AgendaItem.page_number == None  # Items exist but incomplete
            )
        ).limit(AGENDA_BATCH_SIZE).all()

        ids = [c.id for c in to_process]

    # Process each document (each will create its own session)
    for cid in ids:
        segment_document_agenda(cid)

if __name__ == "__main__":
    segment_agendas()
