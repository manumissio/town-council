import datetime
import sys
import os
from urllib.parse import urljoin
from sqlalchemy.orm import sessionmaker

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5

# Ensure we can import from the pipeline module (parent directory)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pipeline.models import db_connect, Event as EventModel


class Dublin(scrapy.spiders.CrawlSpider):
    """
    Spider for Dublin, CA city council meetings.
    Implements delta crawling to fetch only new meetings.
    """
    name = 'dublin'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:dublin'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

        urls = ['http://dublinca.gov/1604/Meetings-Agendas-Minutes-Video-on-Demand']

        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):

        def get_agenda_url(relative_urls):
            full_url = []
            if relative_urls:
                for url in relative_urls:
                    base_url = 'http://dublinca.gov'
                    url = urljoin(base_url, url)
                    full_url.append(url)
                return full_url
            else:
                return None

        table_body = response.xpath('//table/tbody/tr')
        for row in table_body:
            record_date = row.xpath('.//td[@data-th="Date"]/text()').extract_first()
            
            try:
                record_date = datetime.datetime.strptime(record_date, '%B %d, %Y').date()
            except (ValueError, AttributeError):
                self.logger.warning(f"Could not parse date: {record_date}")
                continue

            # DELTA CRAWL CHECK
            if self.last_meeting_date and record_date <= self.last_meeting_date:
                continue

            meeting_type = row.xpath('.//td[@data-th="Meeting Type"]/text()').extract_first()
            agenda_urls = row.xpath('.//td[starts-with(@data-th,"Agenda")]/a/@href').extract()
            agenda_urls = get_agenda_url(agenda_urls)
            minutes_url = row.xpath('.//td[@data-th="Minutes"]/a/@href').extract_first()

            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'Dublin, CA City Council {meeting_type}'.strip(),
                # Use timezone-aware UTC for the scraping timestamp
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=record_date,
                source=self.name.strip(),
                source_url=response.url.strip(),
                meeting_type=meeting_type.strip(),
                )

            # Build the list of documents (agendas, minutes) for this meeting
            documents = []
            for url in agenda_urls:
                agenda_doc = {
                    'url': url,
                    'url_hash': url_to_md5(url),
                    'category': 'agenda'
                }
                documents.append(agenda_doc)

            if minutes_url:
                # Resolve relative URL to an absolute link
                minutes_url = response.urljoin(minutes_url)
                minutes_doc = {
                    'url': minutes_url,
                    'url_hash': url_to_md5(minutes_url),
                    'category': 'minutes'
                }
                documents.append(minutes_doc)

            event['documents'] = documents
            yield event
