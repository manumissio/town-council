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


class Fremont(scrapy.spiders.CrawlSpider):
    """
    Spider for Fremont, CA city council meetings.
    Implements delta crawling to fetch only new meetings.
    """
    name = 'fremont'
    base_url = 'https://fremont.gov/AgendaCenter/'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:fremont'

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

        urls = [self.base_url]

        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):

        def get_agenda_url(relative_urls):
            full_url = []
            if relative_urls:
                for url in relative_urls:
                    if self.base_url not in url:
                        url = urljoin(self.base_url, url)
                    full_url.append(url)
                return full_url
            else:
                return None

        containers = response.xpath(
            '//div[contains(concat(" ", normalize-space(@class), " "), " listing ")]')
        for table in containers:
            table_body = table.xpath('.//table/tbody/tr')
            meeting_type = table.xpath('.//h2/text()').extract_first()
            for row in table_body:
                record_date_str = row.xpath('.//td[1]/h4/a[2]/strong/abbr/text()').extract_first() + \
                    " " + row.xpath('.//td[1]/h4/a[2]/strong/text()').extract_first()
                
                try:
                    record_date = datetime.datetime.strptime(record_date_str, '%b %d, %Y').date()
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not parse date: {record_date_str}")
                    continue

                # DELTA CRAWL CHECK
                if self.last_meeting_date and record_date <= self.last_meeting_date:
                    continue

                agenda_urls = row.xpath(
                    './/td[@class="downloads"]/div/div/div/div/ol/li/a/@href').extract()
                agenda_urls = get_agenda_url(agenda_urls)
                minutes_url = row.xpath('.//td[@class="minutes"]/a/@href').extract_first()

                event = Event(
                    _type='event',
                    ocd_division_id=self.ocd_division_id,
                    name=f'Fremont, CA City Council {meeting_type}',
                    # Use timezone-aware UTC for the scraping timestamp
                    scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                    record_date=record_date,
                    source=self.name,
                    source_url=response.url,
                    meeting_type=meeting_type,
                    )

                # Build the list of documents (agendas, minutes) for this meeting
                documents = []
                if agenda_urls is not None:
                    for url in agenda_urls:
                        agenda_doc = {
                            'url': url,
                            'url_hash': url_to_md5(url),
                            'category': 'agenda'
                        }
                        documents.append(agenda_doc)

                if minutes_url is not None:
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
