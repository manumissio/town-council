import datetime
from urllib.parse import urljoin, quote

import scrapy

from council_crawler.items import Event
from council_crawler.utils import url_to_md5, parse_date_string


class Moraga(scrapy.spiders.CrawlSpider):
    name = 'moraga'
    base_url = 'http://www.moraga.ca.us/council/meetings/2017'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:moraga'

    def start_requests(self):
        urls = [self.base_url]

        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_archive)

    def parse_archive(self, response):

        def get_agenda_url(relative_urls):
            full_url = []
            if relative_urls:
                for url in relative_urls:
                    if self.base_url not in url:
                        # encoding url because several paths have spaces in this crawler
                        url = quote(url)
                        url = urljoin(self.base_url, url)                       
                    full_url.append(url)
                return full_url
            else:
                return None

        table_body = response.xpath('//table/tbody/tr')
        for row in table_body:
            record_date = row.xpath('.//td[1]/text()').extract_first()
            record_date = parse_date_string(record_date)
            agenda_urls = row.xpath('.//td[1]/a/@href').extract()
            agenda_urls = get_agenda_url(agenda_urls)
            meeting_type = row.xpath('.//td[1]/a/text()').extract_first()
            minutes_url = row.xpath(
                './/td[2]/a/@href').extract_first()

            event = Event(
                _type='event',
                ocd_division_id=self.ocd_division_id,
                name=f'Moraga, CA City Council {meeting_type}',
                # Use timezone-aware UTC for the scraping timestamp
                scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
                record_date=record_date,
                source=self.name,
                source_url=response.url,
                meeting_type=meeting_type,
            )

            # Build the list of documents (agendas, minutes) for this meeting
            documents = []
            if agenda_urls is not None:
                for url in agenda_urls:
                    agenda_doc = {
                        'media_type': 'application/pdf',
                        'url': url,
                        'url_hash': url_to_md5(url),
                        'category': 'agenda'
                    }
                    documents.append(agenda_doc)

            if minutes_url is not None:
                # response.urljoin handles relative links and encoding automatically
                minutes_url = response.urljoin(minutes_url)
                minutes_doc = {
                    'media_type': 'application/pdf',
                    'url': minutes_url,
                    'url_hash': url_to_md5(minutes_url),
                    'category': 'minutes'
                }
                documents.append(minutes_doc)

            event['documents'] = documents
            yield event
