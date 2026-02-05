import sys
import os
import pytest

# Add project root and pipeline dir to path so we can import modules
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from council_crawler.council_crawler.utils import url_to_md5, parse_date_string
from pipeline.extractor import is_safe_path

def test_url_to_md5():
    """Verify that URL hashing is consistent and correct."""
    url = "https://example.com/agenda.pdf"
    expected = "00700660666066606660666066606660" # Placeholder, let's use real md5
    import hashlib
    real_expected = hashlib.md5(url.encode()).hexdigest()
    assert url_to_md5(url) == real_expected

def test_parse_date_string_valid():
    """Verify that various date formats are parsed correctly."""
    assert parse_date_string("2026-02-10").day == 10
    assert parse_date_string("February 10, 2026").month == 2
    assert parse_date_string("02/10/26").year == 2026

def test_parse_date_string_invalid():
    """Verify that invalid dates return None instead of crashing."""
    assert parse_date_string("Not a date") is None
    assert parse_date_string("") is None

def test_is_safe_path():
    """Verify the path traversal protection logic."""
    # Mocking the base directory which is usually '../data' relative to extractor.py
    # In the real code, it resolves to an absolute path.
    
    # Let's get the real project root for testing
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(root, 'data')
    
    # Safe path
    safe = os.path.join(data_dir, 'us', 'ca', 'belmont', 'file.pdf')
    assert is_safe_path(safe) is True
    
    # Unsafe paths (trying to go up levels)
    unsafe = os.path.join(data_dir, '..', '..', 'etc', 'passwd')
    assert is_safe_path(unsafe) is False
    
    # Unsafe path outside of data
    outside = "/tmp/malicious.pdf"
    assert is_safe_path(outside) is False
