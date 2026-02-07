import datetime
import scrapy
from council_crawler.utils import url_to_md5
from .base import BaseCitySpider

class Fremont(BaseCitySpider):
    """
    Spider for Fremont, CA city council meetings.
    
    Refactored to use 'BaseCitySpider' for core infrastructure.
    """
    name = 'fremont'
    base_url = 'https://fremont.gov/AgendaCenter/'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:fremont'

    def start_requests(self):
        yield scrapy.Request(url=self.base_url, callback=self.parse_archive)

    def parse_archive(self, response):
        containers = response.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " listing ")]')
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

                # Use Base Class helper for Delta Crawling check
                if self.should_skip_meeting(record_date):
                    continue

                agenda_urls = row.xpath('.//td[@class="downloads"]/div/div/div/div/ol/li/a/@href').extract()
                minutes_url = row.xpath('.//td[@class="minutes"]/a/@href').extract_first()

                # Build the list of documents (agendas, minutes) for this meeting
                documents = []
                for url in agenda_urls:
                    if self.base_url not in url:
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

