import datetime
from urllib.parse import urljoin

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string


class Belmont(scrapy.spiders.CrawlSpider):
    """
    Spider for Belmont, CA city council meetings.
    """
    name = 'belmont'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:belmont'

    def start_requests(self):

        urls = ['http://www.belmont.gov/city-hall/city-government/city-meetings/-toggle-all']

        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):
        table_body = response.xpath('//table/tbody/tr')
        for row in table_body:
            meeting_type=row.xpath('.//span[@itemprop="summary"]/text()').extract_first()
            date_time = row.xpath('.//td[@class="event_datetime"]/text()').extract_first()
            agenda_url = row.xpath('.//td[@class="event_agenda"]//a/@href').extract_first()
            event_minutes_url = row.xpath('.//td[@class="event_minutes"]/a/@href').extract_first()

            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'Belmont, CA City Council {meeting_type}',
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=parse_date_string(date_time),
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
