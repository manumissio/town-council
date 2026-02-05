import datetime
import scrapy
from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string

class BerkeleyCustom(scrapy.Spider):
    """
    Custom spider for Berkeley, CA using their main civic portal table structure.
    """
    name = 'berkeley'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:berkeley'

    def start_requests(self):
        url = 'https://berkeleyca.gov/your-government/city-council/city-council-agendas'
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        """
        Extracts meeting details from the Berkeley Agendas table.
        
        How it works:
        1. It finds all the rows (<tr>) in the meeting table.
        2. For each row, it pulls out the meeting name and date.
        3. It scans the row for any PDF links (Agendas or Packets).
        4. It creates an 'Event' object for our pipeline to process.
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
            
            # 3. Documents
            # We look for links pointing to .pdf files in the table columns
            doc_links = row.xpath('.//td[contains(@class, "views-field")]//a[contains(@href, ".pdf")]')
            
            documents = []
            for link in doc_links:
                url = response.urljoin(link.xpath('./@href').extract_first())
                text = "".join(link.xpath('.//text()').extract()).lower()
                
                # Determine if the PDF is an Agenda or a Minutes/Packet
                category = 'agenda'
                if 'packet' in text or 'minutes' in text:
                    category = 'minutes' # We treat 'Packets' as high-value docs like minutes

                documents.append({
                    'url': url,
                    'url_hash': url_to_md5(url),
                    'category': category
                })

            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'Berkeley, CA City Council {meeting_type.strip()}',
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=record_date,
                source='berkeley',
                source_url=response.url,
                meeting_type=meeting_type.strip()
            )
            event['documents'] = documents
            yield event
