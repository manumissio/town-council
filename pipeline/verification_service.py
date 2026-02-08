import logging
from sqlalchemy.orm import sessionmaker
from pipeline.models import db_connect, AgendaItem, Catalog, Document
from pipeline.utils import find_text_coordinates
from rapidfuzz import fuzz

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verification-service")

# Database Setup
engine = db_connect()
SessionLocal = sessionmaker(bind=engine)

class VerificationService:
    """
    Reconciles official API records (Ground Truth) with PDF content.
    
    Why this is needed:
    To provide a 'Verified' badge on search results and ensure deep-link accuracy.
    """
    
    def __init__(self):
        self.db = SessionLocal()

    def verify_all(self):
        """Processes all items that have ground truth but no spatial alignment yet."""
        items = self.db.query(AgendaItem).filter(
            AgendaItem.raw_history != None,
            AgendaItem.spatial_coords == None
        ).all()
        
        logger.info(f"Found {len(items)} items pending spatial verification.")
        
        for item in items:
            self.verify_item(item)
            
    def verify_item(self, item):
        """
        Attempts to find the API action text within the physical PDF.

        What this does:
        - We have official voting text from the city's API (the "ground truth")
        - We also have a PDF with the same information
        - This function finds WHERE in the PDF that text appears (page number and coordinates)
        - This lets us show users exactly where to look in the document
        """
        try:
            # STEP 1: Get the PDF file path from our catalog
            catalog = self.db.get(Catalog, item.catalog_id)
            if not catalog or not catalog.location:
                return  # Can't verify without a PDF file

            # STEP 2: Search for the official text inside the PDF
            # We use the first 60 characters as a "search anchor"
            # (Sometimes the API and PDF text differ slightly due to formatting)
            search_anchor = item.raw_history[:60].strip()
            locations = find_text_coordinates(catalog.location, search_anchor)

            if locations:
                # SUCCESS: We found exactly where this text appears in the PDF!
                logger.info(f"Verified item: {item.title[:40]}... found on page {locations[0]['page']}")

                # Save the coordinates (page number, x, y position)
                item.spatial_coords = locations

                # If the API has a clearer result than what we extracted, use it
                if item.votes and item.votes.get("result"):
                    item.result = item.votes["result"]

                # COMMIT: Save the verification to the database
                self.db.commit()
            else:
                # FALLBACK: If exact match failed, try searching for just the vote tally
                # (Sometimes "Ayes: Smith, Jones" appears even if other text differs)
                import re
                tally_match = re.search(r"Ayes:.*", item.raw_history)

                if tally_match:
                    alt_search = tally_match.group(0)[:50]
                    locations = find_text_coordinates(catalog.location, alt_search)

                    if locations:
                        logger.info(f"Verified item (alt-search): {item.title[:40]}...")
                        item.spatial_coords = locations
                        # COMMIT: Save the verification result
                        self.db.commit()
                    else:
                        # We couldn't find the text anywhere in the PDF
                        logger.warning(f"Could not locate ground truth in PDF for item {item.id}")

        except Exception as e:
            # ROLLBACK: If anything failed (file read error, database error, etc.),
            # undo any partial database changes to prevent saving corrupted data
            self.db.rollback()
            logger.error(f"Error verifying item {item.id}: {e}")

if __name__ == "__main__":
    service = VerificationService()
    service.verify_all()
