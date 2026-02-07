import sys
import os
import pytest
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

def test_berkeley_custom_parsing():
    """
    Test: Does the new Berkeley portal spider extract data correctly?
    The Berkeley website uses a specific table structure with 'stack' classes.
    """
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