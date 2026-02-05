import datetime
import sys
import os
from sqlalchemy.orm import sessionmaker

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string

# Add project root to path for pipeline imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pipeline.models import db_connect, Event as EventModel


class Dublin(scrapy.Spider):
    """
    Spider for Dublin, CA city meetings.
    
    Logic Flow:
    1. Identify the meeting archive table.
    2. Extract the Date, Meeting Name, and Document Links (PDF).
    3. Categorize the meeting into a 'Body' (e.g. Planning Commission).
    4. Implement Delta Crawling to only fetch new data.
    """
    name = 'dublin'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:dublin'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_meeting_date = self._get_last_meeting_date()
        if self.last_meeting_date:
            self.logger.info(f"Delta crawling enabled. Starting from: {self.last_meeting_date}")

    def _get_last_meeting_date(self):
        """Find the date of the most recent Dublin meeting in our database."""
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            session = Session()
            result = session.query(EventModel.record_date)\
                .filter(EventModel.ocd_division_id == self.ocd_division_id)\
                .order_by(EventModel.record_date.desc())\
                .first()
            session.close()
            return result[0] if result else None
        except Exception as e:
            self.logger.warning(f"Database connection skipped ({e}). Running full crawl.")
            return None

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
            if not record_date:
                continue

            # DELTA CRAWL: Skip if we already have this meeting
            if self.last_meeting_date and record_date <= self.last_meeting_date:
                continue

            # 2. Meeting Type (e.g. "City Council Regular Meeting")
            meeting_name = row.xpath('.//td[@data-th="Meeting Type"]//text()').extract_first()
            if not meeting_name:
                meeting_name = row.xpath('.//td[2]//text()').extract_first()
            
            if not meeting_name:
                continue

            # 3. Organization Mapping (OCD Alignment)
            # We determine which body held the meeting based on the name.
            org_name = "City Council"
            lower_name = meeting_name.lower()
            if "planning" in lower_name:
                org_name = "Planning Commission"
            elif "parks" in lower_name:
                org_name = "Parks & Recreation Commission"
            elif "human" in lower_name:
                org_name = "Human Services Commission"

            # 4. Document Links (Agendas and Minutes)
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

            # 5. Create the Event Item
            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'Dublin, CA {meeting_name.strip()}',
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=record_date,
                source='dublin',
                source_url=response.url,
                meeting_type=meeting_name.strip()
            )
            # The 'organization_name' will be picked up by the pipeline backfill or crawler logic
            event['documents'] = documents
            
            yield event