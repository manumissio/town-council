from .base import TableArchiveSpider


class Fremont(TableArchiveSpider):
    """Spider for Fremont, CA city council meetings."""

    name = 'fremont'
    base_url = 'https://fremont.gov/AgendaCenter/'
    ocd_division_id = 'ocd-division/country:us/state:ca/place:fremont'
    start_url = base_url
    container_selector = (
        '//div[contains(concat(" ", normalize-space(@class), " "), " listing ")]'
    )
    container_meeting_type_selector = './/h2/text()'
    row_selector = './/table/tbody/tr'
    date_selectors = (
        './/td[1]/h4/a[2]/strong/abbr/text()',
        './/td[1]/h4/a[2]/strong/text()',
    )
    date_format = '%b %d, %Y'
    agenda_selector = './/td[@class="downloads"]/div/div/div/div/ol/li/a/@href'
    minutes_selector = './/td[@class="minutes"]/a/@href'
    agenda_all = True
