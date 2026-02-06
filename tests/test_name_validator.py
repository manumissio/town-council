import pytest
from pipeline.utils import is_likely_human_name

def test_valid_human_names():
    """Verify that real names pass the validation."""
    assert is_likely_human_name("Drew Finke") is True
    assert is_likely_human_name("Jane Doe") is True
    assert is_likely_human_name("John A. Smith") is True
    assert is_likely_human_name("Jesse Arreguín") is True

def test_invalid_junk_names():
    """Verify that common municipal junk strings are blocked."""
    assert is_likely_human_name("Teleconference Location") is False
    assert is_likely_human_name("City Clerk") is False
    assert is_likely_human_name("Formal Bid Solicitations") is False
    assert is_likely_human_name("http://example.com") is False
    assert is_likely_human_name("mailto:council@city.gov") is False

def test_numeric_noise_blocking():
    """Verify that document references with numbers are blocked."""
    assert is_likely_human_name("Page 2") is False
    assert is_likely_human_name("Item 4.3") is False
    assert is_likely_human_name("Ordinance 7760-N.S.") is False

def test_short_name_blocking():
    """Verify that single words or too-short strings are blocked."""
    assert is_likely_human_name("John") is False # No space
    assert is_likely_human_name("JD") is False # Too short
    assert is_likely_human_name("") is False
    assert is_likely_human_name(None) is False
