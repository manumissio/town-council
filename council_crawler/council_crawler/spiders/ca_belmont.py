import datetime
import scrapy
from council_crawler.utils import url_to_md5, parse_date_string
from .base import BaseCitySpider

class Belmont(BaseCitySpider):
    """
    Spider for Belmont, CA city council meetings.
    
    Refactored to use 'BaseCitySpider' for core infrastructure.
    """
    name = 'belmont'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:belmont'

    def start_requests(self):
        url = 'http://www.belmont.gov/city-hall/city-government/city-meetings/-toggle-all'
        yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):
        table_body = response.xpath('//table/tbody/tr')
        for row in table_body:
            meeting_type = row.xpath('.//span[@itemprop="summary"]/text()').extract_first()
            date_time_str = row.xpath('.//td[@class="event_datetime"]/text()').extract_first()
            
            # Parse the date from the website
            record_date = parse_date_string(date_time_str)
            
            # Use Base Class helper for Delta Crawling check
            if self.should_skip_meeting(record_date):
                continue

            agenda_url = row.xpath('.//td[@class="event_agenda"]//a/@href').extract_first()
            minutes_url = row.xpath('.//td[@class="event_minutes"]/a/@href').extract_first()

            documents = []
            if agenda_url:
                agenda_url = response.urljoin(agenda_url)
                documents.append({
                    'url': agenda_url,
                    'url_hash': url_to_md5(agenda_url),
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

