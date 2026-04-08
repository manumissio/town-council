from __future__ import annotations

import logging
import re
from importlib import import_module
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError

from pipeline.agenda_verification_model_access import (
    AgendaItemRecord,
    AgendaVerificationSession,
    load_catalog_for_verification,
    open_verification_session,
    select_pending_verification_items,
)

logger = logging.getLogger("verification-service")
SEARCH_ANCHOR_LENGTH = 60
ALTERNATE_TALLY_SEARCH_LENGTH = 50
TALLY_SEARCH_PATTERN = r"Ayes:.*"


class VerificationCoordinateFinder(Protocol):
    def __call__(self, pdf_path: str, search_text: str) -> list[dict[str, object]]: ...


def _new_session() -> AgendaVerificationSession:
    return open_verification_session()


def _find_verification_locations(pdf_path: str, search_text: str) -> list[dict[str, object]]:
    utils_module = import_module("pipeline.utils")
    find_text_coordinates: VerificationCoordinateFinder = utils_module.find_text_coordinates
    return find_text_coordinates(pdf_path, search_text)


class VerificationService:
    """
    Reconciles official API records (Ground Truth) with PDF content.

    Why this is needed:
    To provide a 'Verified' badge on search results and ensure deep-link accuracy.
    """

    def verify_all(self) -> None:
        """Processes all items that have ground truth but no spatial alignment yet."""
        db = _new_session()
        try:
            items = select_pending_verification_items(db)

            logger.info("Found %s items pending spatial verification.", len(items))

            for item in items:
                self.verify_item(item, db=db)
        finally:
            db.close()

    def verify_item(
        self,
        item: AgendaItemRecord,
        *,
        db: AgendaVerificationSession | None = None,
    ) -> None:
        """
        Attempts to find the API action text within the physical PDF.

        What this does:
        - We have official voting text from the city's API (the "ground truth")
        - We also have a PDF with the same information
        - This function finds WHERE in the PDF that text appears (page number and coordinates)
        - This lets us show users exactly where to look in the document
        """
        owns_session = db is None
        session = db or _new_session()

        try:
            # STEP 1: Get the PDF file path from our catalog
            catalog = load_catalog_for_verification(session, catalog_id=item.catalog_id)
            if not catalog or not catalog.location:
                return  # Can't verify without a PDF file

            # STEP 2: Search for the official text inside the PDF
            # We use the first 60 characters as a "search anchor"
            # (Sometimes the API and PDF text differ slightly due to formatting)
            raw_history = item.raw_history or ""
            search_anchor = raw_history[:SEARCH_ANCHOR_LENGTH].strip()
            locations = _find_verification_locations(catalog.location, search_anchor)

            if locations:
                # SUCCESS: We found exactly where this text appears in the PDF!
                title_prefix = (item.title or "")[:40]
                logger.info("Verified item: %s... found on page %s", title_prefix, locations[0]["page"])

                # Save the coordinates (page number, x, y position)
                item.spatial_coords = locations

                # If the API has a clearer result than what we extracted, use it
                if item.votes and item.votes.get("result"):
                    item.result = str(item.votes["result"])

                # COMMIT: Save the verification to the database
                session.commit()
            else:
                # FALLBACK: If exact match failed, try searching for just the vote tally
                # (Sometimes "Ayes: Smith, Jones" appears even if other text differs)
                tally_match = re.search(TALLY_SEARCH_PATTERN, raw_history)

                if tally_match:
                    alt_search = tally_match.group(0)[:ALTERNATE_TALLY_SEARCH_LENGTH]
                    locations = _find_verification_locations(catalog.location, alt_search)

                    if locations:
                        logger.info("Verified item (alt-search): %s...", (item.title or "")[:40])
                        item.spatial_coords = locations
                        # COMMIT: Save the verification result
                        session.commit()
                    else:
                        # We couldn't find the text anywhere in the PDF
                        logger.warning("Could not locate ground truth in PDF for item %s", item.id)

        except (SQLAlchemyError, OSError, ValueError) as exc:
            # Verification service errors: What can fail during PDF verification?
            # - SQLAlchemyError: Database error saving verification results
            # - OSError: PDF file missing, corrupted, or unreadable
            # - ValueError: Invalid coordinates or malformed PDF structure
            # Swallowing is safe here because verification is best-effort enrichment.
            # Rolling back preserves the invariant that partially verified coordinates
            # are never persisted as if they were trustworthy.
            session.rollback()
            logger.exception("Error verifying item %s: %s", item.id, exc)
        finally:
            if owns_session:
                session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    service = VerificationService()
    service.verify_all()
