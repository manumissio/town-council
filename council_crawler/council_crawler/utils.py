import hashlib
from dateutil import parser

def url_to_md5(url):
    m = hashlib.md5()
    m.update(url.encode())
    return m.hexdigest()

def parse_date_string(date_string):
    """
    Finds a date in a string and returns it as a date object.
    
    Why this is needed:
    City websites use many different date formats. This utility handles
    the conversion so the spiders can compare meeting dates reliably.
    """
    if not date_string:
        return None
    
    # Normalize separators for better parsing
    date_string = date_string.replace("-", "/")
    
    try:
        # fuzzy=True allows finding dates within longer strings
        dt = parser.parse(date_string, fuzzy=True)
        # Return only the date part (no time) for consistent DB comparison
        return dt.date()
    except (ValueError, OverflowError):
        return None
