import pytest
import sys
import os
import json
from scrapy.http import TextResponse, Request

# Setup paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'council_crawler'))

from council_crawler.spiders.ca_cupertino import Cupertino
from templates.legistar_api import LegistarApi

def test_cupertino_api_parsing(mocker):
    """
    Test: Does the Cupertino spider correctly parse Legistar API JSON?
    """
    # Mock the database check to return None (full crawl)
    mocker.patch.object(LegistarApi, '_get_last_meeting_date', return_value=None)
    spider = Cupertino()
    
    # Mock JSON response from Legistar
    mock_data = [
        {
            "EventBodyName": "Planning Commission",
            "EventDate": "2026-02-10T00:00:00",
            "EventAgendaFile": "https://cupertino.legistar.com/agenda.pdf",
            "EventMinutesFile": "https://cupertino.legistar.com/minutes.pdf",
            "EventInSiteURL": "https://cupertino.legistar.com/MeetingDetail.aspx?ID=1"
        },
        {
            "EventBodyName": "City Council",
            "EventDate": "2026-02-03T00:00:00",
            "EventAgendaFile": "https://cupertino.legistar.com/cc_agenda.pdf",
            "EventMinutesFile": None,
            "EventInSiteURL": "https://cupertino.legistar.com/MeetingDetail.aspx?ID=2"
        }
    ]
    
    url = 'https://webapi.legistar.com/v1/cupertino/events'
    response = TextResponse(
        url=url, 
        body=json.dumps(mock_data), 
        encoding='utf-8', 
        request=Request(url=url)
    )
    
    # Run the parse method
    results = list(spider.parse(response))
    
    # Verify results
    assert len(results) == 2
    
    # Check Planning Commission meeting
    m1 = results[0]
    assert m1['meeting_type'] == "Planning Commission"
    assert m1['record_date'].year == 2026
    assert len(m1['documents']) == 2
    assert m1['documents'][0]['category'] == 'agenda'
    assert m1['documents'][1]['category'] == 'minutes'
    
    # Check City Council meeting
    m2 = results[1]
    assert m2['meeting_type'] == "City Council"
    assert len(m2['documents']) == 1
    assert m2['documents'][0]['url'] == "https://cupertino.legistar.com/cc_agenda.pdf"
