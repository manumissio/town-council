from urllib.parse import quote

from scrapy.http import Response

from .base import TableArchiveSpider


class Moraga(TableArchiveSpider):
    """Spider for Town of Moraga, CA meetings."""

    name = 'moraga'
    base_url = 'http://www.moraga.ca.us/council/meetings/2017'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:moraga'
    start_url = base_url
    row_selector = '//table/tbody/tr'
    meeting_type_selector = './/td[1]/a/text()'
    date_selectors = ('.//td[1]/text()',)
    agenda_selector = './/td[1]/a/@href'
    minutes_selector = './/td[2]/a/@href'
    agenda_all = True

    def _resolve_agenda_url(self, response: Response, agenda_url: str) -> str:
        if self.base_url in agenda_url:
            return agenda_url
        return response.urljoin(quote(agenda_url))
