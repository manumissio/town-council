import sys
import os
import pytest

# Setup: Add the project folders to the Python path so we can import our code.
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))
sys.path.append(os.path.join(root_dir, 'council_crawler'))

from council_crawler.utils import url_to_md5, parse_date_string
from pipeline.extractor import is_safe_path
from pipeline.utils import generate_ocd_id
import re

def test_ocd_id_format():
    """
    Test: Ensure generated OCD-IDs follow the standard format.
    Format: ocd-[type]/[uuid4]
    """
    item_id = generate_ocd_id('agendaitem')
    assert item_id.startswith('ocd-agendaitem/')
    
    # Extract UUID part
    uuid_part = item_id.split('/')[-1]
    # Simple regex for UUID v4
    uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    assert re.match(uuid_regex, uuid_part)

def test_url_to_md5():
    """
    Test: Does the URL hasher work correctly?
    We want to make sure every URL gets a unique, consistent ID.
    """
    url = "https://example.com/agenda.pdf"
    import hashlib
    # We manually calculate what the MD5 hash SHOULD be.
    real_expected = hashlib.md5(url.encode()).hexdigest()
    # Then we check if our function gives the same result.
    assert url_to_md5(url) == real_expected

def test_parse_date_string_valid():
    """
    Test: Can we handle different date formats from city websites?
    Spiders see "2026-02-10", "February 10", etc. We need to parse them all.
    """
    # Check standard ISO format
    assert parse_date_string("2026-02-10").day == 10
    # Check natural language format
    assert parse_date_string("February 10, 2026").month == 2
    # Check short US format
    assert parse_date_string("02/10/26").year == 2026

def test_parse_date_string_invalid():
    """
    Test: Do we handle garbage data without crashing?
    If a website has a broken date, we should return None, not crash the scraper.
    """
    assert parse_date_string("Not a date") is None
    assert parse_date_string("") is None

def test_is_safe_path(monkeypatch):
    """
    Test: Does our security check block "Path Traversal" attacks?
    We must ensure the script only reads files inside the 'data' folder.
    """
    # 1. Setup: Fix the DATA_DIR to a known location for the test.
    test_data_dir = os.path.abspath("/app/data")
    monkeypatch.setenv("DATA_DIR", test_data_dir)
    
    # 2. Test a "Safe" path: a file that is actually inside the data folder.
    safe = os.path.join(test_data_dir, 'us', 'ca', 'belmont', 'file.pdf')
    assert is_safe_path(safe) is True
    
    # 3. Test an "Unsafe" path: trying to use "../.." to peek at system files.
    # Note: We must use the absolute path because the function uses os.path.abspath.
    unsafe = os.path.abspath(os.path.join(test_data_dir, '..', '..', 'etc', 'passwd'))
    assert is_safe_path(unsafe) is False
    
    # 4. Test a completely outside path.
    outside = "/tmp/malicious.pdf"
    assert is_safe_path(outside) is False