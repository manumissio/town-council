import datetime
import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string
from .base import BaseCitySpider

class Dublin(BaseCitySpider):
    """
    Spider for Dublin, CA city meetings.
    
    Refactored to use 'BaseCitySpider' for core infrastructure.
    """
    name = 'dublin'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:dublin'

    def start_requests(self):
        # The main meeting portal for Dublin, CA
        url = 'https://www.dublinca.gov/1604/Meetings-Agendas-Minutes-Video-on-Demand'
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        """
        Parses the CivicPlus-style meeting table.
        Dublin uses 'data-th' attributes in their table rows.
        """
        # Look for rows in the archive table
        rows = response.xpath('//table//tr[td]')
        self.logger.info(f"Found {len(rows)} potential meeting rows")

        for row in rows:
            # 1. Date Extraction (e.g. "January 20, 2026")
            date_str = row.xpath('.//td[@data-th="Date"]//text()').extract_first()
            if not date_str:
                # Fallback if they changed the data-th name
                date_str = row.xpath('.//td[1]//text()').extract_first()
            
            record_date = parse_date_string(date_str)
            
            # Use Base Class helper for Delta Crawling check
            if self.should_skip_meeting(record_date):
                continue

            # 2. Meeting Type (e.g. "City Council Regular Meeting")
            meeting_name = row.xpath('.//td[@data-th="Meeting Type"]//text()').extract_first()
            if not meeting_name:
                meeting_name = row.xpath('.//td[2]//text()').extract_first()
            
            if not meeting_name:
                continue

            # 3. Document Links (Agendas and Minutes)
            documents = []
            
            # Find all PDF links in the row
            links = row.xpath('.//a[contains(@href, ".pdf")]')
            for link in links:
                href = link.xpath('./@href').extract_first()
                text = "".join(link.xpath('.//text()').extract()).lower()
                
                url = response.urljoin(href)
                
                category = 'agenda'
                if 'minutes' in text:
                    category = 'minutes'
                
                documents.append({
                    'url': url,
                    'url_hash': url_to_md5(url),
                    'category': category
                })

            # 4. Create the Event Item using Base Class Factory
            yield self.create_event_item(
                meeting_date=record_date,
                meeting_name=meeting_name,
                source_url=response.url,
                documents=documents
            )