import datetime
import sys
import os
import scrapy
from sqlalchemy.orm import sessionmaker

# Add project root to path for pipeline imports
# This ensures we can find the 'pipeline' folder even when running from inside 'council_crawler'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pipeline.models import db_connect, Event as EventModel
from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string

class BaseCitySpider(scrapy.Spider):
    """
    A foundational parent class for all City Spiders.
    
    Why this exists:
    Instead of every city spider needing to know how to connect to the database,
    check for duplicates, or format dates, this Base Class handles the 'plumbing'.
    
    Novice Developer Note:
    When you create a new city spider (e.g. 'San Jose'), you inherit from this class.
    You only need to write the code that is specific to San Jose (like finding the table rows),
    and this class will handle the rest.
    """
    
    # These should be set by the child class
    name = None # e.g. 'dublin'
    ocd_division_id = None # e.g. 'ocd-division/country:us/state:ca/place:dublin'
    timezone = 'America/Los_Angeles' # Default to CA time
    
    def __init__(self, *args, **kwargs):
        """
        Sets up the spider and prepares 'Delta Crawling'.
        
        Delta Crawling means: "Only get meetings we don't have yet."
        It saves time and bandwidth.
        """
        super().__init__(*args, **kwargs)
        
        # Verify required attributes are set by the child class
        if not self.ocd_division_id:
            # We log a warning but don't crash, allowing for testing
            self.logger.warning("BaseCitySpider: 'ocd_division_id' is not set. Database checks will fail.")

        self.last_meeting_date = self._get_last_meeting_date()
        
        if self.last_meeting_date:
            self.logger.info(f"Delta crawling enabled. Skipping meetings before: {self.last_meeting_date}")
        else:
            self.logger.info("No previous meetings found. Running full crawl.")

    def _get_last_meeting_date(self):
        """
        Connects to the database to find the date of the most recent meeting we have saved.
        """
        if not self.ocd_division_id:
            return None
            
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            session = Session()
            
            # Query: "Give me the newest 'record_date' for this specific city."
            result = (session.query(EventModel.record_date)
                .filter(EventModel.ocd_division_id == self.ocd_division_id)
                .order_by(EventModel.record_date.desc())
                .first())
            
            session.close()
            # result is a tuple like (datetime.date(2023, 1, 15), )
            return result[0] if result else None
            
        except Exception as e:
            # If the DB is down or tables don't exist, we just crawl everything. Safe failover.
            self.logger.warning(f"Database connection check skipped ({e}). Running full crawl.")
            return None

    def should_skip_meeting(self, meeting_date):
        """
        Helper function to decide if a meeting should be processed.
        
        Returns:
            True if we already have this meeting (and should skip it).
            False if it is new.
        """
        if not meeting_date:
            return True # Skip invalid dates
            
        if self.last_meeting_date and meeting_date <= self.last_meeting_date:
            return True
            
        return False

    def create_event_item(self, meeting_date, meeting_name, source_url, documents, meeting_type=None):
        """
        Factory method to create a standardized Event object.
        Ensures all spiders return data in the exact same format.
        """
        return Event(
            _type='event',
            ocd_division_id=self.ocd_division_id,
            name=f"{self.name.title()}, CA {meeting_name.strip()}", # Standardized Name
            scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
            record_date=meeting_date,
            source=self.name,
            source_url=source_url,
            meeting_type=(meeting_type or meeting_name).strip(),
            documents=documents
        )
