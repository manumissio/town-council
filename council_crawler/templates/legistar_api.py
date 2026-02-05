import datetime
import sys
import os
import json
from sqlalchemy.orm import sessionmaker

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string

# Ensure we can import from the pipeline module (parent directory)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pipeline.models import db_connect, Event as EventModel


class LegistarApi(scrapy.Spider):
    """
    Spider template for cities using the Legistar Web API.
    This is much more reliable than HTML scraping as it returns structured JSON.
    """
    name = 'legistar_api'
    client_name = '' # e.g. 'cupertino'
    ocd_division_id = ''
    
    def __init__(self, client='', city='', state='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_name = client or city
        self.city_name = city
        self.state = state
        self.ocd_division_id = f'ocd-division/country:us/state:{state.lower()}/place:{city.lower().replace(" ", "_")}'
        
        # Initialize delta crawling
        self.last_meeting_date = self._get_last_meeting_date()
        if self.last_meeting_date:
            self.logger.info(f"Delta crawling enabled. Fetching meetings since: {self.last_meeting_date}")

    def _get_last_meeting_date(self):
        """Retrieve the most recent meeting date from the database."""
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            session = Session()
            result = session.query(EventModel.record_date)\
                .filter(EventModel.ocd_division_id == self.ocd_division_id)\
                .order_by(EventModel.record_date.desc())\
                .first()
            session.close()
            return result[0] if result else None
        except Exception as e:
            self.logger.warning(f"Database check skipped ({e}).")
            return None

    def start_requests(self):
        # We fetch the last 1000 events. In a production system, you'd use OData filters 
        # to only fetch recent ones, but 1000 is a safe start for discovery.
        url = f'https://webapi.legistar.com/v1/{self.client_name}/events?$top=1000&$orderby=EventDate%20desc'
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        data = json.loads(response.text)
        self.logger.info(f"Received {len(data)} events from Legistar API")

        for item in data:
            # 1. Parse Date
            raw_date = item.get('EventDate')
            if not raw_date:
                continue
            
            # Legistar dates look like "2024-07-01T00:00:00"
            record_date = datetime.datetime.fromisoformat(raw_date).date()

            # DELTA CRAWL CHECK
            if self.last_meeting_date and record_date <= self.last_meeting_date:
                continue

            # 2. Extract Metadata
            body_name = item.get('EventBodyName', 'City Council')
            meeting_name = f"{self.city_name.title()}, {self.state.upper()} {body_name} Meeting"
            
            # 3. Handle Documents
            documents = []
            agenda_url = item.get('EventAgendaFile')
            minutes_url = item.get('EventMinutesFile')

            if agenda_url:
                documents.append({
                    'url': agenda_url,
                    'url_hash': url_to_md5(agenda_url),
                    'category': 'agenda'
                })

            if minutes_url:
                documents.append({
                    'url': minutes_url,
                    'url_hash': url_to_md5(minutes_url),
                    'category': 'minutes'
                })

            # 4. Create the Event Item
            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=meeting_name,
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=record_date,
                source=self.client_name,
                source_url=item.get('EventInSiteURL', ''),
                meeting_type=body_name
            )
            event['documents'] = documents
            
            yield event
