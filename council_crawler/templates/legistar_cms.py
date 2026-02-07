import datetime
from council_crawler.spiders.base import BaseCitySpider
from council_crawler.utils import url_to_md5, parse_date_string
import scrapy

class LegistarCms(BaseCitySpider):
    """
    Generic spider template for cities using the Legistar content management system.
    
    This template inherits from BaseCitySpider, which handles the 
    database connection and skipping of old meetings.
    """
    name = 'legistar_cms'
    
    def __init__(self, legistar_url='', city='', state='', *args, **kwargs):
        if not legistar_url:
            raise ValueError('legistar_url is required.')
        if not city:
            raise ValueError('city is required')
        if not state:
            raise ValueError('state is required.')
            
        self.start_urls = [legistar_url]
        self.name = city.lower() # Used as the 'source' in the database
        self.ocd_division_id = f'ocd-division/country:us/state:{state.lower()}/place:{self.name.replace(" ", "_")}'
        
        super().__init__(*args, **kwargs)

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):
        # Look for the main results table. Legistar standard uses 'rgMasterTable' class.
        table_body = response.xpath('//table[contains(@class, "rgMasterTable")]/tbody/tr')
        
        if not table_body:
            self.logger.warning(f"No meeting rows found on {response.url}.")
            return

        for row in table_body:
            # We extract the meeting type and date from the table columns.
            meeting_type = row.xpath('.//td[1]//text()[normalize-space()]').extract_first()
            date = row.xpath('.//td[2]//text()[normalize-space()]').extract_first()
            time = row.xpath('.//td[4]//text()[normalize-space()]').extract_first()
            
            if not meeting_type or not date:
                continue

            date_time = f'{date} {time}'
            record_date = parse_date_string(date_time)

            # Use the BaseCitySpider to check if we should skip this meeting
            if self.should_skip_meeting(record_date):
                continue

            # Look for Agenda and Minutes links.
            agenda_url = row.xpath('.//td[7]//a/@href').extract_first()
            minutes_url = row.xpath('.//td[8]//a/@href').extract_first()

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

