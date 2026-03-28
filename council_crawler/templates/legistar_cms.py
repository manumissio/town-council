import datetime
import re
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
    historical_year_cookie_value = 'Last Year'
    
    def __init__(self, legistar_url='', city='', state='', *args, **kwargs):
        if not legistar_url:
            raise ValueError('legistar_url is required.')
        if not city:
            raise ValueError('city is required')
        if not state:
            raise ValueError('state is required.')

        self.start_urls = [legistar_url]
        # Canonical source identity must stay slug-shaped so downstream onboarding
        # and search filters do not depend on human-readable spacing variants.
        self.city_display_name = city
        self.name = city.lower().replace(" ", "_")
        self.ocd_division_id = f'ocd-division/country:us/state:{state.lower()}/place:{self.name}'

        super().__init__(*args, **kwargs)

    def create_event_item(self, meeting_date, meeting_name, source_url, documents, meeting_type=None):
        event = super().create_event_item(
            meeting_date=meeting_date,
            meeting_name=meeting_name,
            source_url=source_url,
            documents=documents,
            meeting_type=meeting_type,
        )
        event['name'] = f"{self.city_display_name.title()}, CA {meeting_name.strip()}"
        return event

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse_calendar_window)

    def parse_calendar_window(self, response):
        year_cookie_name, year_cookie_value = self._extract_calendar_year_cookie(response)

        # CMS tenants default this cookie to "This Month", which truncates the
        # server-rendered grid to the current window and hides the historical
        # rows we need for delta crawling.
        if year_cookie_name and year_cookie_value == 'This Month':
            self.logger.debug(
                "Requesting wider Legistar CMS calendar window via %s=%s on %s",
                year_cookie_name,
                self.historical_year_cookie_value,
                response.url,
            )
            yield response.follow(
                response.url,
                callback=self.parse_archive,
                cookies={year_cookie_name: self.historical_year_cookie_value},
                dont_filter=True,
            )
            return

        yield from self.parse_archive(response)

    def _extract_calendar_year_cookie(self, response):
        for header in response.headers.getlist('Set-Cookie'):
            match = re.search(
                r'(Setting-\d+-Calendar Year)=([^;]+)',
                header.decode('latin1'),
            )
            if match:
                return match.group(1), match.group(2)
        return None, None

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
