import sys
import os
import pytest
import scrapy
from scrapy.http import HtmlResponse
import datetime

# Setup: Add all necessary folders to the Python path.
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))
sys.path.append(os.path.join(root_dir, 'council_crawler'))

# Import the actual scraper classes.
from council_crawler.spiders.ca_belmont import Belmont
from council_crawler.spiders.ca_berkeley import BerkeleyCustom
from templates.legistar_cms import LegistarCms

def test_berkeley_custom_parsing(mocker):
    """
    Test: Does the new Berkeley portal spider extract data correctly?
    The Berkeley website uses a specific table structure with 'stack' classes.
    """
    # Mock DB: Prevent database connection attempts
    mocker.patch('council_crawler.spiders.base.BaseCitySpider._get_last_meeting_date', return_value=None)
    
    spider = BerkeleyCustom()
    
    url = "https://berkeleyca.gov/your-government/city-council/city-council-agendas"
    body = """
    <table class="stack">
      <tbody>
        <tr>
          <td class="council-meeting-name">Regular City Council Meeting</td>
          <td class="views-field-field-daterange">02/10/2026</td>
          <td class="views-field-field-agenda"><a href="agenda_link.pdf">Agenda</a></td>
          <td class="views-field-field-minutes"><a href="packet_link.pdf">Agenda Packet</a></td>
        </tr>
      </tbody>
    </table>
    """
    response = HtmlResponse(url=url, body=body, encoding='utf-8')
    
    items = list(spider.parse(response))
    
    assert len(items) == 1
    event = items[0]
    assert "Berkeley, CA City Council Regular City Council Meeting" == event['name']
    assert event['record_date'].day == 10
    assert len(event['documents']) == 2
    # Ensure the 'Packet' is correctly categorized as a minutes/high-value doc
    packet_doc = next(d for d in event['documents'] if 'packet' in d['url'])
    assert packet_doc['category'] == 'minutes'

def test_belmont_spider_parsing(mocker):
    """
    Test: Can the Belmont spider read a meeting row from HTML?
    We provide a snippet of HTML and check if the spider extracts the right fields.
    """
    # 1. Mock: Prevent the spider from trying to talk to the real database during startup.
    mocker.patch('council_crawler.spiders.ca_belmont.Belmont._get_last_meeting_date', return_value=None)
    
    spider = Belmont()
    
    # 2. Mock Data: This is what the Belmont website HTML looks like.
    url = "http://www.belmont.gov/meetings"
    body = """
    <table>
      <tbody>
        <tr>
          <td><span itemprop="summary">Regular Meeting</span></td>
          <td class="event_datetime">2026-02-10</td>
          <td class="event_agenda"><a href="agenda.pdf">Agenda</a></td>
          <td class="event_minutes"><a href="minutes.pdf">Minutes</a></td>
        </tr>
      </tbody>
    </table>
    """
    # Wrap the HTML in a Scrapy 'Response' object.
    response = HtmlResponse(url=url, body=body, encoding='utf-8')
    
    # 3. Action: Run the spider's 'parse' logic on our mock HTML.
    items = list(spider.parse_archive(response))
    
    # 4. Verify: Did it find the meeting?
    assert len(items) == 1
    event = items[0]
    assert event['name'] == "Belmont, CA City Council Regular Meeting"
    assert event['meeting_type'] == "Regular Meeting"
    assert len(event['documents']) == 2 # 1 Agenda + 1 Minutes

def test_legistar_template_parsing(mocker):
    """
    Test: Does our generic 'Legistar' template work for other cities?
    Many cities use the same 'Legistar' software. We test if our generic parser
    can handle their specific (and messy) HTML structure.
    """
    # 1. Mock: Disable database check.
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    
    # Initialize the spider for a dummy city.
    spider = LegistarCms(legistar_url='https://test.legistar.com', city='testcity', state='ca')
    
    # 2. Mock Data: Legistar uses specific table classes and nested tags.
    url = "https://test.legistar.com/Calendar.aspx"
    body = """
    <table class="rgMasterTable">
      <tbody>
        <tr>
          <td><font><a href="#"><font>Regular Meeting</font></a></font></td>
          <td><font>2/10/2026</font></td>
          <td></td>
          <td><font><span><font>6:00 PM</font></span></font></td>
          <td></td><td></td>
          <td><font><span><a href="agenda.pdf">Agenda</a></span></font></td>
          <td><font><span><a href="minutes.pdf"><font>Minutes</font></a></span></font></td>
        </tr>
      </tbody>
    </table>
    """
    response = HtmlResponse(url=url, body=body, encoding='utf-8')
    
    # 3. Action: Parse the HTML.
    items = list(spider.parse_archive(response))
    
    # 4. Verify: Check if the generic template extracted the date and title correctly.
    assert len(items) == 1
    event = items[0]
    assert "Testcity, CA" in event['name']
    assert event['meeting_type'] == "Regular Meeting"
    assert event['documents'][0]['category'] == 'agenda'
    assert event['documents'][1]['category'] == 'minutes'

def test_legistar_template_maps_documents_by_header_for_rich_cms_tables(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com', city='hayward', state='ca')

    response = HtmlResponse(
        url='https://test.legistar.com/Calendar.aspx',
        body="""
        <table class="rgMasterTable">
          <thead>
            <tr>
              <th>Name</th>
              <th>Meeting Date</th>
              <th>Unused</th>
              <th>Meeting Time</th>
              <th>Meeting Details</th>
              <th>Staff/Project</th>
              <th>Applicant Presentations</th>
              <th>Agenda</th>
              <th>Accessible Agenda</th>
              <th>Agenda Packet</th>
              <th>Action Minutes</th>
              <th>Accessible Minutes</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>City Council</td>
              <td>7/22/2025</td>
              <td></td>
              <td>7:00 PM</td>
              <td><a href="detail.html">Meeting details</a></td>
              <td>None</td>
              <td><a href="presentation.pdf">Presentation</a></td>
              <td><a href="agenda.pdf">Agenda</a></td>
              <td>None</td>
              <td>None</td>
              <td><a href="minutes.pdf">Action Minutes</a></td>
              <td>None</td>
            </tr>
            <tr>
              <td>Planning Commission</td>
              <td>7/24/2025</td>
              <td></td>
              <td>7:00 PM</td>
              <td><a href="detail-2.html">Meeting details</a></td>
              <td>None</td>
              <td>None</td>
              <td><a href="agenda-only.pdf">Agenda</a></td>
              <td>None</td>
              <td>None</td>
              <td>None</td>
              <td>None</td>
            </tr>
          </tbody>
        </table>
        """,
        encoding='utf-8',
    )

    items = list(spider.parse_archive(response))

    assert len(items) == 2
    assert items[0]['documents'] == [
        {
            'url': 'https://test.legistar.com/agenda.pdf',
            'url_hash': items[0]['documents'][0]['url_hash'],
            'category': 'agenda',
        },
        {
            'url': 'https://test.legistar.com/minutes.pdf',
            'url_hash': items[0]['documents'][1]['url_hash'],
            'category': 'minutes',
        },
    ]
    assert items[1]['documents'] == [
        {
            'url': 'https://test.legistar.com/agenda-only.pdf',
            'url_hash': items[1]['documents'][0]['url_hash'],
            'category': 'agenda',
        }
    ]

def test_legistar_template_expands_default_this_month_window(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com/Calendar.aspx', city='testcity', state='ca')

    response = HtmlResponse(
        url='https://test.legistar.com/Calendar.aspx',
        body='<html></html>',
        encoding='utf-8',
        headers={
            'Set-Cookie': [
                b'Setting-270-Calendar Year=This Month; path=/; secure',
                b'Setting-270-Calendar Body=All; path=/; secure',
            ],
        },
    )

    requests = list(spider.parse_calendar_window(response))

    assert len(requests) == 1
    follow_up = requests[0]
    assert isinstance(follow_up, scrapy.Request)
    assert follow_up.url == 'https://test.legistar.com/Calendar.aspx'
    assert follow_up.cookies == {'Setting-270-Calendar Year': 'Last Year'}
    assert follow_up.dont_filter is True
    assert follow_up.callback == spider.parse_archive

def test_legistar_template_does_not_expand_when_year_cookie_already_broad(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com/Calendar.aspx', city='testcity', state='ca')

    url = "https://test.legistar.com/Calendar.aspx"
    body = """
    <table class="rgMasterTable">
      <tbody>
        <tr>
          <td><font><a href="#"><font>Regular Meeting</font></a></font></td>
          <td><font>2/10/2026</font></td>
          <td></td>
          <td><font><span><font>6:00 PM</font></span></font></td>
          <td></td><td></td>
          <td><font><span><a href="agenda.pdf">Agenda</a></span></font></td>
          <td><font><span><a href="minutes.pdf"><font>Minutes</font></a></span></font></td>
        </tr>
      </tbody>
    </table>
    """
    response = HtmlResponse(
        url=url,
        body=body,
        encoding='utf-8',
        headers={'Set-Cookie': [b'Setting-270-Calendar Year=Last Year; path=/; secure']},
    )

    items = list(spider.parse_calendar_window(response))

    assert len(items) == 1
    assert items[0]['meeting_type'] == "Regular Meeting"


def test_legistar_template_traverses_grid_calendar_pager(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com/Calendar.aspx', city='sunnyvale', state='ca')

    response = HtmlResponse(
        url='https://test.legistar.com/Calendar.aspx',
        body="""
        <html>
          <body>
            <form>
              <input type="hidden" name="__VIEWSTATE" value="state-1" />
              <input type="hidden" name="__EVENTVALIDATION" value="valid-1" />
              <input type="hidden" name="ctl00_ContentPlaceHolder1_gridCalendar_ClientState" value="grid-state" />
              <input id="ctl00_ContentPlaceHolder1_lstYears_Input" value="2025" />
              <table id="ctl00_ContentPlaceHolder1_gridCalendar_ctl00" class="rgMasterTable">
                <tbody>
                  <tr>
                    <td><font><a href="#"><font>Regular Meeting</font></a></font></td>
                    <td><font>7/16/2025</font></td>
                    <td></td>
                    <td><font><span><font>6:00 PM</font></span></font></td>
                    <td></td><td></td>
                    <td><font><span><a href="agenda.pdf">Agenda</a></span></font></td>
                    <td><font><span><a href="minutes.pdf"><font>Minutes</font></a></span></font></td>
                  </tr>
                </tbody>
              </table>
              <a class="rgCurrentPage" href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridCalendar$ctl00$ctl02$ctl00$ctl02','')"
                 onclick="Telerik.Web.UI.Grid.NavigateToPage('ctl00_ContentPlaceHolder1_gridCalendar_ctl00', '1'); return false;">1</a>
              <a href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridCalendar$ctl00$ctl02$ctl00$ctl04','')"
                 onclick="Telerik.Web.UI.Grid.NavigateToPage('ctl00_ContentPlaceHolder1_gridCalendar_ctl00', '2'); return false;">2</a>
            </form>
          </body>
        </html>
        """,
        encoding='utf-8',
        request=scrapy.Request(
            url='https://test.legistar.com/Calendar.aspx',
            cookies={'Setting-270-Calendar Year': '2025'},
        ),
    )

    results = list(spider.parse_archive(response))

    assert len(results) == 2
    assert results[0]['record_date'] == datetime.date(2025, 7, 16)
    follow_up = results[1]
    assert isinstance(follow_up, scrapy.FormRequest)
    assert follow_up.method == 'POST'
    assert follow_up.cookies == {'Setting-270-Calendar Year': '2025'}
    assert "__EVENTTARGET=ctl00%24ContentPlaceHolder1%24gridCalendar%24ctl00%24ctl02%24ctl00%24ctl04" in follow_up.body.decode()
    assert "__VIEWSTATE=state-1" in follow_up.body.decode()
    assert follow_up.meta['visited_calendar_pages'] == {('2025', 1)}


def test_legistar_template_parses_older_rows_from_follow_up_page(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com/Calendar.aspx', city='sunnyvale', state='ca')

    response = HtmlResponse(
        url='https://test.legistar.com/Calendar.aspx',
        body="""
        <html>
          <body>
            <input id="ctl00_ContentPlaceHolder1_lstYears_Input" value="2025" />
            <table id="ctl00_ContentPlaceHolder1_gridCalendar_ctl00" class="rgMasterTable">
              <tbody>
                <tr>
                  <td><font><a href="#"><font>Regular Meeting</font></a></font></td>
                  <td><font>5/13/2025</font></td>
                  <td></td>
                  <td><font><span><font>6:00 PM</font></span></font></td>
                  <td></td><td></td>
                  <td><font><span><a href="agenda-older.pdf">Agenda</a></span></font></td>
                  <td><font><span><a href="minutes-older.pdf"><font>Minutes</font></a></span></font></td>
                </tr>
              </tbody>
            </table>
            <a href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridCalendar$ctl00$ctl02$ctl00$ctl02','')"
               onclick="Telerik.Web.UI.Grid.NavigateToPage('ctl00_ContentPlaceHolder1_gridCalendar_ctl00', '2'); return false;"
               class="rgCurrentPage">2</a>
          </body>
        </html>
        """,
        encoding='utf-8',
        request=scrapy.Request(url='https://test.legistar.com/Calendar.aspx'),
    )

    results = list(spider.parse_archive(response))

    assert len(results) == 1
    assert results[0]['record_date'] == datetime.date(2025, 5, 13)
    assert results[0]['documents'][0]['url'] == 'https://test.legistar.com/agenda-older.pdf'


def test_legistar_template_stops_when_next_pager_state_already_visited(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com/Calendar.aspx', city='sunnyvale', state='ca')

    request = scrapy.Request(url='https://test.legistar.com/Calendar.aspx')
    request.meta['visited_calendar_pages'] = {('2025', 1), ('2025', 2)}
    response = HtmlResponse(
        url='https://test.legistar.com/Calendar.aspx',
        body="""
        <html>
          <body>
            <input id="ctl00_ContentPlaceHolder1_lstYears_Input" value="2025" />
            <table id="ctl00_ContentPlaceHolder1_gridCalendar_ctl00" class="rgMasterTable">
              <tbody>
                <tr>
                  <td><font><a href="#"><font>Regular Meeting</font></a></font></td>
                  <td><font>7/16/2025</font></td>
                  <td></td>
                  <td><font><span><font>6:00 PM</font></span></font></td>
                  <td></td><td></td>
                  <td><font><span><a href="agenda.pdf">Agenda</a></span></font></td>
                  <td><font><span><a href="minutes.pdf"><font>Minutes</font></a></span></font></td>
                </tr>
              </tbody>
            </table>
            <a class="rgCurrentPage" href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridCalendar$ctl00$ctl02$ctl00$ctl02','')"
               onclick="Telerik.Web.UI.Grid.NavigateToPage('ctl00_ContentPlaceHolder1_gridCalendar_ctl00', '1'); return false;">1</a>
            <a href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridCalendar$ctl00$ctl02$ctl00$ctl04','')"
               onclick="Telerik.Web.UI.Grid.NavigateToPage('ctl00_ContentPlaceHolder1_gridCalendar_ctl00', '2'); return false;">2</a>
          </body>
        </html>
        """,
        encoding='utf-8',
        request=request,
    )

    results = list(spider.parse_archive(response))

    assert len(results) == 1
    assert results[0]['record_date'] == datetime.date(2025, 7, 16)


def test_legistar_template_targets_grid_calendar_when_multiple_grids_exist(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com/Calendar.aspx', city='sunnyvale', state='ca')

    response = HtmlResponse(
        url='https://test.legistar.com/Calendar.aspx',
        body="""
        <html>
          <body>
            <input type="hidden" name="__VIEWSTATE" value="state-1" />
            <input id="ctl00_ContentPlaceHolder1_lstYears_Input" value="2025" />
            <table id="ctl00_ContentPlaceHolder1_gridUpcomingMeetings_ctl00" class="rgMasterTable">
              <tbody>
                <tr>
                  <td><font><a href="#"><font>Upcoming Meeting</font></a></font></td>
                  <td><font>4/1/2026</font></td>
                  <td></td>
                  <td><font><span><font>6:00 PM</font></span></font></td>
                  <td></td><td></td>
                  <td><font><span><a href="upcoming-agenda.pdf">Agenda</a></span></font></td>
                  <td><font><span><a href="upcoming-minutes.pdf"><font>Minutes</font></a></span></font></td>
                </tr>
              </tbody>
            </table>
            <table id="ctl00_ContentPlaceHolder1_gridCalendar_ctl00" class="rgMasterTable">
              <tbody>
                <tr>
                  <td><font><a href="#"><font>Regular Meeting</font></a></font></td>
                  <td><font>7/16/2025</font></td>
                  <td></td>
                  <td><font><span><font>6:00 PM</font></span></font></td>
                  <td></td><td></td>
                  <td><font><span><a href="agenda.pdf">Agenda</a></span></font></td>
                  <td><font><span><a href="minutes.pdf"><font>Minutes</font></a></span></font></td>
                </tr>
              </tbody>
            </table>
            <a class="rgCurrentPage" href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridCalendar$ctl00$ctl02$ctl00$ctl02','')"
               onclick="Telerik.Web.UI.Grid.NavigateToPage('ctl00_ContentPlaceHolder1_gridCalendar_ctl00', '1'); return false;">1</a>
            <a href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridCalendar$ctl00$ctl02$ctl00$ctl04','')"
               onclick="Telerik.Web.UI.Grid.NavigateToPage('ctl00_ContentPlaceHolder1_gridCalendar_ctl00', '2'); return false;">2</a>
          </body>
        </html>
        """,
        encoding='utf-8',
    )

    results = list(spider.parse_archive(response))

    assert len(results) == 2
    assert results[0]['meeting_type'] == "Regular Meeting"
    assert results[0]['record_date'] == datetime.date(2025, 7, 16)


def test_legistar_template_normalizes_slug_source_but_keeps_display_name(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    spider = LegistarCms(legistar_url='https://test.legistar.com', city='san mateo', state='ca')

    event = spider.create_event_item(
        meeting_date=datetime.date(2026, 2, 10),
        meeting_name="Regular Meeting",
        source_url="https://test.legistar.com/Calendar.aspx",
        documents=[],
        meeting_type="Regular Meeting",
    )

    assert event['source'] == "san_mateo"
    assert event['ocd_division_id'] == "ocd-division/country:us/state:ca/place:san_mateo"
    assert event['name'] == "San Mateo, CA Regular Meeting"

def test_base_city_spider_disable_delta_bypasses_existing_anchor(mocker):
    from council_crawler.spiders.base import BaseCitySpider

    mocker.patch('council_crawler.spiders.base.BaseCitySpider._get_last_meeting_date', return_value=datetime.date(2026, 1, 1))

    class TestSpider(BaseCitySpider):
        name = 'test_city'
        ocd_division_id = 'ocd-division/test'

    spider = TestSpider(disable_delta='true')

    assert spider.disable_delta is True
    assert spider.last_meeting_date is None
    assert spider.should_skip_meeting(datetime.date(2025, 12, 31)) is False
    assert spider.should_skip_meeting(datetime.date(2026, 1, 1)) is False

def test_base_city_spider_disable_delta_parses_bool_values():
    from council_crawler.spiders.base import BaseCitySpider

    assert BaseCitySpider._parse_bool_arg('true', arg_name='disable_delta') is True
    assert BaseCitySpider._parse_bool_arg('YES', arg_name='disable_delta') is True
    assert BaseCitySpider._parse_bool_arg('0', arg_name='disable_delta') is False
    assert BaseCitySpider._parse_bool_arg(None, arg_name='disable_delta') is False

    with pytest.raises(ValueError, match='disable_delta must be one of'):
        BaseCitySpider._parse_bool_arg('maybe', arg_name='disable_delta')

def test_legistar_template_inherits_disable_delta_behavior(mocker):
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=datetime.date(2026, 1, 1))
    spider = LegistarCms(
        legistar_url='https://test.legistar.com/Calendar.aspx',
        city='testcity',
        state='ca',
        disable_delta='true',
    )

    response = HtmlResponse(
        url='https://test.legistar.com/Calendar.aspx',
        body="""
        <table class="rgMasterTable">
          <tbody>
            <tr>
              <td><font><a href="#"><font>Regular Meeting</font></a></font></td>
              <td><font>12/10/2025</font></td>
              <td></td>
              <td><font><span><font>6:00 PM</font></span></font></td>
              <td></td><td></td>
              <td><font><span><a href="agenda.pdf">Agenda</a></span></font></td>
              <td><font><span><a href="minutes.pdf"><font>Minutes</font></a></span></font></td>
            </tr>
          </tbody>
        </table>
        """,
        encoding='utf-8',
    )

    items = list(spider.parse_archive(response))

    assert spider.disable_delta is True
    assert len(items) == 1
    assert items[0]['record_date'] == datetime.date(2025, 12, 10)

def test_belmont_delta_crawl(mocker):
    """
    Test: Does 'Delta Crawling' skip meetings we already have?
    This is critical for performance—we don't want to re-download the same files daily.
    """
    # 1. Mock Setup: Assume the database already has meetings up to Feb 5th.
    last_date = datetime.date(2026, 2, 5)
    mocker.patch('council_crawler.spiders.ca_belmont.Belmont._get_last_meeting_date', return_value=last_date)
    
    spider = Belmont()
    # Ensure the spider 'knows' the last date.
    assert spider.last_meeting_date == last_date
    
    # 2. Mock Response: We provide 1 OLD meeting (Feb 1st) and 1 NEW meeting (Feb 10th).
    url = "http://www.belmont.gov/meetings"
    body = """
    <table>
      <tbody>
        <tr>
          <td><span itemprop="summary">Old Meeting</span></td>
          <td class="event_datetime">2026-02-01</td>
          <td class="event_agenda"><a href="old.pdf">Agenda</a></td>
          <td class="event_minutes"></td>
        </tr>
        <tr>
          <td><span itemprop="summary">New Meeting</span></td>
          <td class="event_datetime">2026-02-10</td>
          <td class="event_agenda"><a href="new.pdf">Agenda</a></td>
          <td class="event_minutes"></td>
        </tr>
      </tbody>
    </table>
    """
    response = HtmlResponse(url=url, body=body, encoding='utf-8')
    
    # 3. Action: Parse both meetings.
    items = list(spider.parse_archive(response))
    
    # 4. Verify: Only the NEW meeting should be returned. 
    # The Feb 1st meeting is older than our Feb 5th cut-off, so it should be skipped.
    assert len(items) == 1
    assert items[0]['meeting_type'] == "New Meeting"

def test_base_city_spider_logic(mocker):
    """
    Test: Does the new 'BaseCitySpider' parent class handle logic correctly?
    We create a temporary child class to test the inherited methods.
    """
    from council_crawler.spiders.base import BaseCitySpider
    
    # 1. Mock DB: Prevent database connection attempts
    mocker.patch('council_crawler.spiders.base.BaseCitySpider._get_last_meeting_date', return_value=datetime.date(2026, 1, 1))
    
    # Create a dummy spider that inherits from BaseCitySpider
    class TestSpider(BaseCitySpider):
        name = 'test_city'
        ocd_division_id = 'ocd-division/test'
        
    spider = TestSpider()
    
    # 2. Test Delta Crawling Logic (should_skip_meeting)
    # Date is OLDER than last_meeting_date (Jan 1, 2026) -> Skip
    assert spider.should_skip_meeting(datetime.date(2025, 12, 31)) is True
    # Date is SAME as last_meeting_date -> Skip
    assert spider.should_skip_meeting(datetime.date(2026, 1, 1)) is True
    # Date is NEWER -> Keep
    assert spider.should_skip_meeting(datetime.date(2026, 1, 2)) is False
    # Date is None -> Skip
    assert spider.should_skip_meeting(None) is True

    # 3. Test Event Factory (create_event_item)
    event = spider.create_event_item(
        meeting_date=datetime.date(2026, 2, 1),
        meeting_name="Test Meeting ", # Note the trailing space to test stripping
        source_url="http://example.com",
        documents=[]
    )
    
    assert event['name'] == "Test_City, CA Test Meeting" # Name title-cased + formatted
    assert event['meeting_type'] == "Test Meeting" # Stripped
    assert event['source'] == "test_city"

def test_dublin_refactored_parsing(mocker):
    """
    Test: Does the refactored Dublin spider (using BaseCitySpider) still parse correctly?
    We load the 'mock_dublin.html' file and feed it to the spider.
    """
    from council_crawler.spiders.ca_dublin import Dublin
    
    # 1. Mock DB: Disable delta crawling check for this test
    mocker.patch('council_crawler.spiders.base.BaseCitySpider._get_last_meeting_date', return_value=None)
    
    spider = Dublin()
    
    # 2. Load Mock HTML
    mock_path = os.path.join(os.path.dirname(__file__), 'mock_dublin.html')
    with open(mock_path, 'r') as f:
        body = f.read()
        
    response = HtmlResponse(url="https://dublin.ca.gov/archive", body=body, encoding='utf-8')
    
    # 3. Parse
    items = list(spider.parse(response))
    
    # 4. Verify
    # The mock file contains 2 meetings: Jan 20 (Council) and Jan 13 (Planning)
    assert len(items) == 2
    
    council_meeting = items[0]
    assert council_meeting['record_date'] == datetime.date(2026, 1, 20)
    assert "City Council Regular Meeting" in council_meeting['name']
    assert len(council_meeting['documents']) == 2 # Agenda + Minutes
    
    planning_meeting = items[1]
    assert planning_meeting['record_date'] == datetime.date(2026, 1, 13)
    assert "Planning Commission Meeting" in planning_meeting['name']
    assert len(planning_meeting['documents']) == 1 # Agenda only
