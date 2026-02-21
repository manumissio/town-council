import os
import time
import requests
import logging
import re
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import db_connect, Place, Event, AgendaItem

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ground-truth-sync")

# Database Setup
engine = db_connect()
SessionLocal = sessionmaker(bind=engine)

class GroundTruthSync:
    """
    Synchronizes 'Ground Truth' data (official votes/actions) from Legistar API.
    
    Why this exists:
    PDF extraction can be imprecise. By fetching the official record from the API, 
    we create a 'Golden Record' to validate our PDF segments against.
    """
    
    def __init__(self):
        self.session = requests.Session()

    def get_city_name(self, place):
        """Standardizes city name for Legistar API (e.g. 'mountain_view' -> 'mountainview')"""
        return place.name.lower().replace("_", "").replace(" ", "")

    def parse_votes(self, action_text):
        """
        Parses the semi-structured 'Action Text' into a structured vote object.
        """
        if not action_text:
            return None
            
        votes = {"result": None, "ayes": [], "noes": [], "absent": [], "abstain": []}
        
        # 1. Extract Result
        result_match = re.search(r"(carried|failed|was approved|was denied|adopted)", action_text, re.IGNORECASE)
        if result_match:
            votes["result"] = result_match.group(1).lower()

        # 2. Extract Sections
        # We look for the literal markers and take everything until the NEXT marker or a known end-of-list sentence
        markers = [
            ("ayes", r"Ayes?\s*:"),
            ("noes", r"Noes?\s*:"),
            ("absent", r"Absent\s*:"),
            ("abstain", r"Abstain\s*:")
        ]
        
        # Find all marker starts
        found_markers = []
        for key, pattern in markers:
            for m in re.finditer(pattern, action_text, re.IGNORECASE):
                found_markers.append((m.start(), m.end(), key))
        found_markers.sort()

        for i, (start, end, key) in enumerate(found_markers):
            # The content starts after the current marker
            content_start = end
            # The content ends at the start of the next marker OR the end of the text
            if i + 1 < len(found_markers):
                content_end = found_markers[i+1][0]
            else:
                content_end = len(action_text)
            
            content = action_text[content_start:content_end].strip()
            # Remove trailing periods if they aren't part of a name (e.g. "Wei.")
            content = re.sub(r"\.\s*$", "", content)
            
            # Split by comma or 'and'
            # We use a non-regex split first to see if it's cleaner
            raw_parts = re.split(r",\s*|\s+and\s+", content)
            for p in raw_parts:
                p = p.strip()
                # Clean up "and " if it leaked through
                p = re.sub(r"^and\s+", "", p, flags=re.IGNORECASE)
                if p.lower() not in ["none", ""] and not p.isdigit():
                    votes[key].append(p)
                
        return votes

    def sync_all(self):
        """Iterates through cities and fetches history for recent events."""
        with SessionLocal() as db:
            places = db.query(Place).filter(Place.legistar_client != None).all()

            for place in places:
                city_api_name = place.legistar_client
                logger.info(f"Processing city: {place.name} (API: {city_api_name})")

                # Fetch events for this city that have documents
                events = db.query(Event).filter(Event.place_id == place.id).order_by(Event.record_date.desc()).all()

                for event in events:
                    self.sync_event_history(db, city_api_name, event)
                    # Friendly Neighbor Throttling: respect the API
                    time.sleep(0.5)

    def sync_event_history(self, db, city_api_name, event):
        """Fetches history for all items in an event by finding the Legistar EventId first."""
        # 1. Fetch recent events from API to find a date match
        api_url = f"https://webapi.legistar.com/v1/{city_api_name}/events?$filter=EventDate eq datetime'{event.record_date.isoformat()}'"
        
        try:
            res = self.session.get(api_url, timeout=10)
            if res.status_code != 200: return
            
            api_events = res.json()
            if not api_events:
                logger.warning(f"No Legistar event found for {city_api_name} on {event.record_date}")
                return
                
            # Usually the first one is the main council meeting
            event_id = api_events[0].get("EventId")
            
            # 2. Fetch the items for this event
            items_url = f"https://webapi.legistar.com/v1/{city_api_name}/events/{event_id}/EventItems"
            response = self.session.get(items_url, timeout=10)
            if response.status_code != 200: return
                
            items = response.json()
            logger.info(f"Syncing {len(items)} items for {city_api_name} event on {event.record_date}")
            
            for item_data in items:
                matter_id = item_data.get("EventItemMatterId")
                if not matter_id: continue
                    
                title = item_data.get("EventItemTitle", "")
                # Clean title for better matching (Legistar often has extra whitespace)
                clean_api_title = " ".join(title.split()).lower()
                
                # Use RapidFuzz to find the best match in the local DB for this event
                # This handles cases where the PDF title and API title differ by a few characters.
                from rapidfuzz import process, fuzz
                
                local_items = db.query(AgendaItem).filter(AgendaItem.event_id == event.id).all()
                if not local_items: continue
                
                # Create a mapping of title -> item for the matcher
                title_to_item = {item.title: item for item in local_items}
                
                # Find the best match
                match_results = process.extractOne(
                    clean_api_title, 
                    title_to_item.keys(), 
                    scorer=fuzz.token_sort_ratio
                )
                
                if match_results and match_results[1] > 85: # 85% confidence threshold
                    matched_title = match_results[0]
                    local_item = title_to_item[matched_title]
                    
                    # Only fetch if we haven't already stored the official record
                    if not local_item.raw_history:
                        self.fetch_matter_history(db, city_api_name, matter_id, local_item)
                        time.sleep(0.1)  # Brief pause to be respectful to the API

        except (requests.RequestException, SQLAlchemyError, ValueError) as e:
            # Ground truth sync errors: What can fail during API synchronization?
            # - requests.RequestException: Legistar API down, timeout, network error
            # - SQLAlchemyError: Database error saving fetched data
            # - ValueError: Malformed API response, invalid date format
            # Why continue on error? One city's API failure shouldn't stop syncing others
            # The failed city will be retried on the next sync run
            logger.error(f"Error syncing {city_api_name} event on {event.record_date}: {e}")

    def fetch_matter_history(self, db, city_name, matter_id, agenda_item):
        """
        Fetches the detailed history/votes for a specific matter.

        This function makes changes to the database, so we need to be careful:
        - If everything works: we commit() to save the changes permanently
        - If something fails: we rollback() to undo any partial changes
        """
        url = f"https://webapi.legistar.com/v1/{city_name}/matters/{matter_id}/histories"

        try:
            # Ask the Legistar API for the voting history of this agenda item
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                histories = response.json()

                # Loop through the history records from newest to oldest
                # We want to find an action that shows a final decision (carried/passed/adopted)
                for hist in reversed(histories):
                    action_text = hist.get("MatterHistoryActionText")

                    # Check if this history entry has a decisive result
                    if action_text and ("carried" in action_text.lower() or "passed" in action_text.lower() or "adopted" in action_text.lower()):
                        logger.info(f"Found Ground Truth for: {agenda_item.title[:50]}...")

                        # Save the official record to our database
                        agenda_item.raw_history = action_text
                        agenda_item.votes = self.parse_votes(action_text)
                        agenda_item.legistar_matter_id = matter_id

                        # COMMIT: Save these changes to the database permanently
                        db.commit()
                        break  # Stop after finding the first decisive action

        except (requests.RequestException, SQLAlchemyError, KeyError, ValueError) as e:
            # Matter history fetch errors: What can fail when getting vote data?
            # - requests.RequestException: API call failed (timeout, 404, 500 error)
            # - SQLAlchemyError: Database error during commit
            # - KeyError: API response missing expected fields (MatterHistoryActionText)
            # - ValueError: Invalid data format (can't parse votes)
            # Why rollback? If we got partial data, don't save incomplete records
            # ROLLBACK: Undo any partial changes to keep the database in a consistent state
            db.rollback()
            logger.error(f"Error fetching matter {matter_id}: {e}")

if __name__ == "__main__":
    sync = GroundTruthSync()
    sync.sync_all()
