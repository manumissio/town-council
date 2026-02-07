import datetime
import scrapy
from urllib.parse import quote
from council_crawler.utils import url_to_md5, parse_date_string
from .base import BaseCitySpider

class Moraga(BaseCitySpider):
    """
    Spider for Town of Moraga, CA meetings.
    
    Refactored to use 'BaseCitySpider' for core infrastructure.
    """
    name = 'moraga'
    base_url = 'http://www.moraga.ca.us/council/meetings/2017'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:moraga'

    def start_requests(self):
        yield scrapy.Request(url=self.base_url, callback=self.parse_archive)

    def parse_archive(self, response):
        table_body = response.xpath('//table/tbody/tr')
        for row in table_body:
            record_date_str = row.xpath('.//td[1]/text()').extract_first()
            record_date = parse_date_string(record_date_str)

            # Use Base Class helper for Delta Crawling check
            if self.should_skip_meeting(record_date):
                continue

            agenda_urls = row.xpath('.//td[1]/a/@href').extract()
            meeting_type = row.xpath('.//td[1]/a/text()').extract_first()
            minutes_url = row.xpath('.//td[2]/a/@href').extract_first()

            # Build the list of documents (agendas, minutes) for this meeting
            documents = []
            for url in agenda_urls:
                if self.base_url not in url:
                    # encoding url because several paths have spaces in this crawler
                    url = quote(url)
                    url = response.urljoin(url)
                documents.append({
                    'url': url,
                    'url_hash': url_to_md5(url),
                    'category': 'agenda'
                })

            if minutes_url:
                minutes_url = response.urljoin(minutes_url)
                documents.append({
                    'url': minutes_url,
                    'url_hash': url_to_md5(minutes_url),
                    'category': 'minutes'
                })

            # Create the standardized Event Item using the base class factory
            yield self.create_event_item(
                meeting_date=record_date,
                meeting_name=f"City Council {meeting_type}",
                source_url=response.url,
                documents=documents,
                meeting_type=meeting_type
            )

