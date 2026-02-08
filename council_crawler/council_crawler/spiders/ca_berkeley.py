import datetime
import scrapy
from council_crawler.utils import url_to_md5, parse_date_string
from .base import BaseCitySpider

class BerkeleyCustom(BaseCitySpider):
    """
    Custom spider for Berkeley, CA using their main civic portal table structure.
    
    Refactored to use 'BaseCitySpider' for core infrastructure.
    """
    name = 'berkeley'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:berkeley'

    def start_requests(self):
        url = 'https://berkeleyca.gov/your-government/city-council/city-council-agendas'
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        """
        Extracts meeting details from the Berkeley Agendas table.
        """
        # Look for the meeting table rows using CSS classes found on berkeleyca.gov
        rows = response.xpath('//table[contains(@class, "stack")]/tbody/tr')
        self.logger.info(f"Found {len(rows)} meeting rows")

        for row in rows:
            # 1. Meeting Title: e.g., "City Council Regular Meeting"
            meeting_type = row.xpath('.//td[contains(@class, "council-meeting-name")]//text()[normalize-space()]').extract_first()
            # 2. Date: e.g., "02/10/2026"
            date_str = row.xpath('.//td[contains(@class, "views-field-field-daterange")]//text()[normalize-space()]').extract_first()
            
            if not meeting_type or not date_str:
                continue

            # Turn the text date into a standard Python date object
            record_date = parse_date_string(date_str)
            
            # Use Base Class helper for Delta Crawling check
            if self.should_skip_meeting(record_date):
                continue

            # 3. Documents
            # Generic crawl strategy: keep PDF and HTML links.
            # Downstream resolver (Legistar -> HTML -> LLM) decides which source to trust.
            doc_links = row.xpath('.//td[contains(@class, "views-field")]//a[@href]')
            
            documents = []
            for link in doc_links:
                url = response.urljoin(link.xpath('./@href').extract_first())
                text = "".join(link.xpath('.//text()').extract()).lower()
                lowered_url = url.lower()
                is_pdf = ".pdf" in lowered_url
                is_eagenda_html = ("eagenda" in lowered_url or "eagenda" in text) and (
                    ".html" in lowered_url or ".htm" in lowered_url or not is_pdf
                )

                if not is_pdf and not is_eagenda_html:
                    continue
                
                # Determine if the PDF is an Agenda or a Minutes/Packet
                category = 'agenda'
                if is_eagenda_html:
                    category = 'agenda_html'
                if 'packet' in text or 'minutes' in text:
                    category = 'minutes' # We treat 'Packets' as high-value docs like minutes

                documents.append({
                    'url': url,
                    'url_hash': url_to_md5(url),
                    'category': category
                })

            # Create the standardized Event Item using the base class factory
            yield self.create_event_item(
                meeting_date=record_date,
                meeting_name=f"City Council {meeting_type.strip()}",
                source_url=response.url,
                documents=documents
            )
