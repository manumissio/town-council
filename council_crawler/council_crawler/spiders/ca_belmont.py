from .base import TableArchiveSpider


class Belmont(TableArchiveSpider):
    """Spider for Belmont, CA city council meetings."""

    name = 'belmont'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:belmont'
    start_url = 'http://www.belmont.gov/city-hall/city-government/city-meetings/-toggle-all'
    row_selector = '//table/tbody/tr'
    meeting_type_selector = './/span[@itemprop="summary"]/text()'
    date_selectors = ('.//td[@class="event_datetime"]/text()',)
    agenda_selector = './/td[@class="event_agenda"]//a/@href'
    minutes_selector = './/td[@class="event_minutes"]/a/@href'
