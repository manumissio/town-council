import datetime
from urllib.parse import urljoin

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string

class LegistarCms(scrapy.spiders.CrawlSpider):
    """
    Generic spider template for cities using the Legistar content management system.
    """
    name = 'legistar_cms'
    ocd_division_id = ''
    formatted_city_name = ''
    city_name = ''
    urls = []

    def __init__(self, legistar_url='', city='', state='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls = [legistar_url]
        if not self.urls:
            raise ValueError('legistar_url is required.')
        if not city:
            raise ValueError('city is required')

        self.city_name = city.lower()

        if not state:
            raise ValueError('state is required.')
        if len(state) != 2:
            raise ValueError('state must be a two letter abbreviation.')
      
        # Format the city name and OCD ID for standardized tracking
        self.formatted_city_name = f'{self.city_name.capitalize()}, {state.upper()}'
        self.ocd_division_id = f'ocd-division/country:us/state:{state.lower()}/place:{self.city_name.replace(" ", "_")}'

    def start_requests(self):
        for url in self.urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):
        table_body = response.xpath('//table[@class="rgMasterTable"]/tbody/tr')
        for row in table_body:
            # Legistar tables often wrap text in <font> tags which must be accounted for in XPaths
            meeting_type = row.xpath('.//td[1]/font/a/font/text()').extract_first()
            date = row.xpath('.//td[2]/font/text()').extract_first()
            time = row.xpath('.//td[4]/font/span/font/text()').extract_first()
            date_time = f'{date} {time}'
            agenda_url = row.xpath('.//td[7]/font/span/a/@href').extract_first()
            event_minutes_url = row.xpath('.//td[8]/font/span/a/font/text()').extract_first()

            # Filter out placeholder text for unavailable minutes
            if event_minutes_url == 'Not\xa0available':
                event_minutes_url = None

            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'{self.formatted_city_name} City Council {meeting_type}',
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=parse_date_string(date_time),
                source=self.city_name,
                source_url=response.url,
                meeting_type=meeting_type
                )

            documents = []
            if agenda_url is not None:
                # response.urljoin handles relative links and <base> tags automatically
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
