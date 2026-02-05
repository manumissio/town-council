import datetime
from urllib.parse import urljoin
from sqlalchemy.orm import sessionmaker

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string
# Import database connectivity and models
from pipeline.models import db_connect, Event as EventModel

class Belmont(scrapy.spiders.CrawlSpider):
    """
    Spider for Belmont, CA city council meetings.
    Implements delta crawling to only fetch new meetings.
    """
    name = 'belmont'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:belmont'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Determine the last recorded meeting date to enable delta crawling
        self.last_meeting_date = self._get_last_meeting_date()
        if self.last_meeting_date:
            self.logger.info(f"Delta crawling enabled. Last meeting recorded: {self.last_meeting_date}")

    def _get_last_meeting_date(self):
        """Queries the database for the most recent meeting date for this city."""
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            session = Session()
            # Get the max record_date for this specific city
            result = session.query(EventModel.record_date)\
                .filter(EventModel.ocd_division_id == self.ocd_division_id)\
                .order_by(EventModel.record_date.desc())\
                .first()
            session.close()
            return result[0] if result else None
        except Exception as e:
            self.logger.error(f"Could not retrieve last meeting date: {e}")
            return None

    def start_requests(self):
        urls = ['http://www.belmont.gov/city-hall/city-government/city-meetings/-toggle-all']
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):
        table_body = response.xpath('//table/tbody/tr')
        for row in table_body:
            meeting_type=row.xpath('.//span[@itemprop="summary"]/text()').extract_first()
            date_time_str = row.xpath('.//td[@class="event_datetime"]/text()').extract_first()
            
            # Parse the date from the website
            record_date = parse_date_string(date_time_str)
            
            # DELTA CRAWLING LOGIC: 
            # If we already have this meeting (or newer) in the database, skip it.
            if self.last_meeting_date and record_date and record_date <= self.last_meeting_date:
                continue

            agenda_url = row.xpath('.//td[@class="event_agenda"]//a/@href').extract_first()
            event_minutes_url = row.xpath('.//td[@class="event_minutes"]/a/@href').extract_first()

            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'Belmont, CA City Council {meeting_type}',
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=record_date,
                source=self.name,
                source_url=response.url,
                meeting_type=meeting_type
                )

            documents = []
            if agenda_url is not None:
                # response.urljoin automatically resolves relative paths against the current response URL
                agenda_url = response.urljoin(agenda_url)
                agenda_doc = {
                    'url': agenda_url,
                    'url_hash': url_to_md5(agenda_url),
                    'category': 'agenda'
                }
                documents.append(agenda_doc)

            if event_minutes_url is not None:
                event_minutes_url = response.urljoin(event_minutes_url)
                minutes_doc = {
                    'url': event_minutes_url,
                    'url_hash': url_to_md5(event_minutes_url),
                    'category': 'minutes'
                }
                documents.append(minutes_doc)

            event['documents'] = documents
            yield event
