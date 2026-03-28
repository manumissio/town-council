import datetime
import html
import json
from urllib.parse import parse_qs, urlparse

import scrapy

from council_crawler.spiders.base import BaseCitySpider
from council_crawler.utils import url_to_md5

class LegistarApi(BaseCitySpider):
    """
    Spider template for cities using the Legistar Web API.
    
    This template inherits from BaseCitySpider, which handles the 
    database connection and skipping of old meetings.
    """
    name = 'legistar_api'
    client_name = '' # e.g. 'cupertino'
    
    def __init__(self, client='', city='', state='', *args, **kwargs):
        # Use canonical slug identity for storage while keeping the API client
        # name separate so downstream filters are city-shaped, not host-shaped.
        normalized_city = city.lower().replace(" ", "_")
        self.name = normalized_city
        self.client_name = client or normalized_city
        self.city_name = city
        self.state = state
        self.ocd_division_id = f'ocd-division/country:us/state:{state.lower()}/place:{normalized_city}'
        
        super().__init__(*args, **kwargs)

    def start_requests(self):
        # We fetch the last 1000 events from the Legistar API.
        #
        # Important: Legistar's Web API can respond with XML unless we ask for JSON.
        # Scrapy's default Accept header prefers HTML/XML, so we override it here.
        url = f'https://webapi.legistar.com/v1/{self.client_name}/events?$top=1000&$orderby=EventDate%20desc'
        yield scrapy.Request(
            url=url,
            callback=self.parse,
            headers={"Accept": "application/json"},
        )

    def _build_documents(self, *, agenda_url=None, minutes_url=None):
        documents = []
        if agenda_url:
            documents.append({
                'url': agenda_url,
                'url_hash': url_to_md5(agenda_url),
                'category': 'agenda'
            })

        if minutes_url:
            documents.append({
                'url': minutes_url,
                'url_hash': url_to_md5(minutes_url),
                'category': 'minutes'
            })
        return documents

    def _dedupe_documents(self, documents):
        deduped = []
        seen = set()
        for doc in documents:
            key = (doc.get('category'), doc.get('url'))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(doc)
        return deduped

    def _extract_detail_page_documents(self, response):
        agenda_url = None
        minutes_url = None
        for raw_href in response.xpath('//a[@href]/@href').getall():
            href = html.unescape(raw_href or "")
            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            media_type = (query.get("M") or [None])[0]
            if media_type == "A" and agenda_url is None:
                agenda_url = response.urljoin(href)
            elif media_type == "M" and minutes_url is None:
                minutes_url = response.urljoin(href)
        return self._build_documents(agenda_url=agenda_url, minutes_url=minutes_url)

    def _build_event_item(self, *, item, record_date, body_name, documents):
        return self.create_event_item(
            meeting_date=record_date,
            meeting_name=f"{body_name} Meeting",
            source_url=item.get('EventInSiteURL', ''),
            documents=self._dedupe_documents(documents),
            meeting_type=body_name
        )

    def parse_meeting_detail(self, response, *, item, record_date, body_name, api_documents):
        fallback_documents = self._extract_detail_page_documents(response)
        yield self._build_event_item(
            item=item,
            record_date=record_date,
            body_name=body_name,
            documents=api_documents + fallback_documents,
        )

    def parse(self, response):
        # Legistar should return JSON, but in practice we sometimes see:
        # - a UTF-8 BOM prefix
        # - a non-JSON HTML/body when a proxy/WAF returns an error page
        #
        # Use response.text so Scrapy handles decoding, then strip a BOM if present.
        try:
            text = (response.text or "").lstrip("\ufeff")
            data = json.loads(text)
        except (ValueError, json.JSONDecodeError) as e:
            snippet = (getattr(response, "text", "") or "")[:200].replace("\n", "\\n")
            self.logger.error(
                f"Failed to parse JSON from {response.url} (status={getattr(response, 'status', 'unknown')}): {e}. "
                f"Body starts with: {snippet!r}"
            )
            return

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
            agenda_url = item.get('EventAgendaFile')
            minutes_url = item.get('EventMinutesFile')
            documents = self._build_documents(agenda_url=agenda_url, minutes_url=minutes_url)
            source_url = item.get('EventInSiteURL', '')

            # Some Legistar tenants omit file URLs from the API payload even when
            # the meeting detail page still publishes the agenda/minutes links.
            if not documents and source_url:
                yield scrapy.Request(
                    url=source_url,
                    callback=self.parse_meeting_detail,
                    cb_kwargs={
                        "item": item,
                        "record_date": record_date,
                        "body_name": body_name,
                        "api_documents": documents,
                    },
                )
                continue

            # 4. Create the standardized Event Item using the base class factory
            yield self._build_event_item(
                item=item,
                record_date=record_date,
                body_name=body_name,
                documents=documents,
            )
