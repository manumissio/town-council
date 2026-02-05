import datetime
import sys
import os
from urllib.parse import urljoin
from sqlalchemy.orm import sessionmaker

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string

# Ensure we can import from the pipeline module (parent directory)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pipeline.models import db_connect, Event as EventModel


class LegistarCms(scrapy.spiders.CrawlSpider):
    """
    Generic spider template for cities using the Legistar content management system.
    Implements delta crawling to fetch only new meetings.
    """
    name = 'legistar_cms'
    ocd_division_id = ''
    formatted_city_name = ''
    city_name = ''
    urls = []

    def __init__(self, legistar_url='', city='', state='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls = [legistar_url]
        if not self.urls:
            raise ValueError('legistar_url is required.')
        if not city:
            raise ValueError('city is required')

        self.city_name = city.lower()

        if not state:
            raise ValueError('state is required.')
        if len(state) != 2:
            raise ValueError('state must be a two letter abbreviation.')
      
        # Format the city name and OCD ID for standardized tracking
        self.formatted_city_name = f'{self.city_name.capitalize()}, {state.upper()}'
        self.ocd_division_id = f'ocd-division/country:us/state:{state.lower()}/place:{self.city_name.replace(" ", "_")}'

        # Initialize delta crawling
        self.last_meeting_date = self._get_last_meeting_date()
        if self.last_meeting_date:
            self.logger.info(f"Delta crawling enabled. Last meeting recorded: {self.last_meeting_date}")

    def _get_last_meeting_date(self):
        """Retrieve the most recent meeting date from the database for this city."""
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
            self.logger.warning(f"Database connection failed ({e}). Defaulting to full crawl.")
            return None

    def start_requests(self):
        for url in self.urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):
        # Look for the main results table. Legistar standard uses 'rgMasterTable' class.
        table_body = response.xpath('//table[contains(@class, "rgMasterTable")]/tbody/tr')
        
        if not table_body:
            self.logger.warning(f"No meeting rows found on {response.url}. The table might be empty or require a search action.")
            return

        for row in table_body:
            # We use more flexible XPaths that look for text within the cell, 
            # ignoring fragile <font> or <span> tags.
            meeting_type = row.xpath('.//td[1]//text()[normalize-space()]').extract_first()
            date = row.xpath('.//td[2]//text()[normalize-space()]').extract_first()
            time = row.xpath('.//td[4]//text()[normalize-space()]').extract_first()
            
            if not meeting_type or not date:
                continue

            date_time = f'{date} {time}'
            record_date = parse_date_string(date_time)

            # DELTA CRAWL CHECK: Skip if we already have this meeting in the database.
            if self.last_meeting_date and record_date and record_date <= self.last_meeting_date:
                continue

            # Look for Agenda and Minutes links. We look for any <a> tag in the respective columns.
            agenda_url = row.xpath('.//td[7]//a/@href').extract_first()
            # For minutes, we check for a link. Some cities display 'Not available' as text.
            event_minutes_url = row.xpath('.//td[8]//a/@href').extract_first()

            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'{self.formatted_city_name} City Council {meeting_type.strip()}',
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=record_date,
                source=self.city_name,
                source_url=response.url,
                meeting_type=meeting_type.strip()
                )

            documents = []
            if agenda_url:
                agenda_url = response.urljoin(agenda_url)
                documents.append({
                    'url': agenda_url,
                    'url_hash': url_to_md5(agenda_url),
                    'category': 'agenda'
                })

            if event_minutes_url:
                event_minutes_url = response.urljoin(event_minutes_url)
                documents.append({
                    'url': event_minutes_url,
                    'url_hash': url_to_md5(event_minutes_url),
                    'category': 'minutes'
                })

            event['documents'] = documents
            self.logger.info(f"Scraped meeting: {event['name']} on {record_date}")
            yield event
