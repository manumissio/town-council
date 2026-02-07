import datetime
import scrapy
import json

from council_crawler.spiders.base import BaseCitySpider

class LegistarApi(BaseCitySpider):
    """
    Spider template for cities using the Legistar Web API.
    
    This template inherits from BaseCitySpider, which handles the 
    database connection and skipping of old meetings.
    """
    name = 'legistar_api'
    client_name = '' # e.g. 'cupertino'
    
    def __init__(self, client='', city='', state='', *args, **kwargs):
        # We set these before calling super().__init__ so the base class 
        # can use them for the database lookup.
        self.name = client or city
        self.city_name = city
        self.state = state
        self.ocd_division_id = f'ocd-division/country:us/state:{state.lower()}/place:{city.lower().replace(" ", "_")}'
        
        super().__init__(*args, **kwargs)

    def start_requests(self):
        # We fetch the last 1000 events from the Legistar API.
        url = f'https://webapi.legistar.com/v1/{self.name}/events?$top=1000&$orderby=EventDate%20desc'
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        data = json.loads(response.text)
        self.logger.info(f"Received {len(data)} events from Legistar API")

        for item in data:
            # 1. Parse Date
            raw_date = item.get('EventDate')
            if not raw_date:
                continue
            
            # Legistar dates look like "2024-07-01T00:00:00"
            record_date = datetime.datetime.fromisoformat(raw_date).date()

            # Use the BaseCitySpider to check if we should skip this meeting
            if self.should_skip_meeting(record_date):
                continue

            # 2. Extract Metadata
            body_name = item.get('EventBodyName', 'City Council')
            
            # 3. Handle Documents
            documents = []
            agenda_url = item.get('EventAgendaFile')
            minutes_url = item.get('EventMinutesFile')

            if agenda_url:
                from council_crawler.utils import url_to_md5
                documents.append({
                    'url': agenda_url,
                    'url_hash': url_to_md5(agenda_url),
                    'category': 'agenda'
                })

            if minutes_url:
                from council_crawler.utils import url_to_md5
                documents.append({
                    'url': minutes_url,
                    'url_hash': url_to_md5(minutes_url),
                    'category': 'minutes'
                })

            # 4. Create the standardized Event Item using the base class factory
            yield self.create_event_item(
                meeting_date=record_date,
                meeting_name=f"{body_name} Meeting",
                source_url=item.get('EventInSiteURL', ''),
                documents=documents,
                meeting_type=body_name
            )

