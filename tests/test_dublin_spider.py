import pytest
import sys
import os
from scrapy.http import HtmlResponse, Request

# Setup paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'council_crawler'))

from council_crawler.spiders.ca_dublin import Dublin

def test_dublin_spider_parsing():
    """
    Test: Does the Dublin spider correctly parse the meeting table?
    We use a 'mock' HTML file to simulate the city website.
    """
    spider = Dublin()
    
    # Load the mock HTML
    current_dir = os.path.dirname(__file__)
    mock_path = os.path.join(current_dir, 'mock_dublin.html')
    with open(mock_path, 'r') as f:
        html_content = f.read()
    
    # Create a Scrapy response object
    url = 'https://www.dublinca.gov/1604/Meetings-Agendas-Minutes-Video-on-Demand'
    response = HtmlResponse(
        url=url, 
        body=html_content, 
        encoding='utf-8', 
        request=Request(url=url)
    )
    
    # Run the parse method
    results = list(spider.parse(response))
    
    # Verify results
    assert len(results) == 2
    
    # Check the first meeting (City Council)
    m1 = results[0]
    assert m1['record_date'].year == 2026
    assert m1['record_date'].month == 1
    assert m1['record_date'].day == 20
    assert "City Council" in m1['name']
    assert len(m1['documents']) == 2
    
    # Check the second meeting (Planning Commission)
    m2 = results[1]
    assert "Planning Commission" in m2['name']
    assert len(m2['documents']) == 1
    assert m2['documents'][0]['category'] == 'agenda'
