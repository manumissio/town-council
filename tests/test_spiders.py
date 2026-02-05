import sys
import os
import pytest
from scrapy.http import HtmlResponse
import datetime

# Setup paths
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))
sys.path.append(os.path.join(root_dir, 'council_crawler'))

# Import spiders
from council_crawler.spiders.ca_belmont import Belmont
from templates.legistar_cms import LegistarCms

def test_belmont_spider_parsing(mocker):
    """Verify that the Belmont spider correctly parses meeting rows."""
    # 1. Mock _get_last_meeting_date to return None (full crawl)
    mocker.patch('council_crawler.spiders.ca_belmont.Belmont._get_last_meeting_date', return_value=None)
    
    spider = Belmont()
    
    # 2. Create a mock HTML response
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
    response = HtmlResponse(url=url, body=body, encoding='utf-8')
    
    # 3. Call parse_archive
    items = list(spider.parse_archive(response))
    
    # 4. Verify
    assert len(items) == 1
    event = items[0]
    assert event['name'] == "Belmont, CA City Council Regular Meeting"
    assert event['meeting_type'] == "Regular Meeting"
    assert len(event['documents']) == 2

def test_legistar_template_parsing(mocker):
    """Verify that the Legistar template correctly parses meetings."""
    # 1. Mock _get_last_meeting_date
    mocker.patch('templates.legistar_cms.LegistarCms._get_last_meeting_date', return_value=None)
    
    spider = LegistarCms(legistar_url='https://test.legistar.com', city='testcity', state='ca')
    
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
    
    items = list(spider.parse_archive(response))
    
    assert len(items) == 1
    event = items[0]
    assert "Testcity, CA" in event['name']
    assert event['meeting_type'] == "Regular Meeting"

def test_belmont_delta_crawl(mocker):
    """Verify that the delta crawl logic skips old meetings."""
    last_date = datetime.date(2026, 2, 5)
    
    # 1. Mock last meeting date to Feb 5th
    mocker.patch('council_crawler.spiders.ca_belmont.Belmont._get_last_meeting_date', return_value=last_date)
    
    spider = Belmont()
    assert spider.last_meeting_date == last_date
    
    # 2. Mock response with an OLD meeting (Feb 1st) and a NEW meeting (Feb 10th)
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
    
    # 3. Parse
    items = list(spider.parse_archive(response))
    
    # 4. Verify - Only the NEW meeting should be yielded (date > Feb 5th)
    assert len(items) == 1
    assert items[0]['meeting_type'] == "New Meeting"
