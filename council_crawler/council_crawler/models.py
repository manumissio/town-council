import datetime

from sqlalchemy import create_engine
from sqlalchemy import Column, Boolean, String, Integer, Date, DateTime
from sqlalchemy.orm import DeclarativeBase
from council_crawler import settings

# Modern SQLAlchemy 2.0 style: Subclassing DeclarativeBase.
class Base(DeclarativeBase):
    pass


def db_connect():
    """
    Connect using STORAGE_ENGINE from settings.py
    Returns sqlalchemy engine
    """
    return create_engine(settings.STORAGE_ENGINE)


def create_tables(engine):
    """
    Creates all tables defined in this file.
    """
    Base.metadata.create_all(engine)


class Place(Base):
    """
    Represents a City or Town (e.g., "Belmont, CA").
    This table tells the crawler which cities to look for.
    """
    __tablename__ = 'place'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    type_ = Column(String)
    state = Column(String)
    country = Column(String)
    display_name = Column(String)
    ocd_division_id = Column(String, index=True) # Unique ID for the city
    seed_url = Column(String) # Starting URL for the crawler
    hosting_service = Column(String)
    crawler = Column(Boolean, default=False)
    crawler_name = Column(String)
    crawler_type = Column(String)
    crawler_owner = Column(String)


class UrlStage(Base):
    """
    A temporary staging area where the crawler saves links to PDF files.
    The downloader pipeline reads from here later.
    """
    __tablename__ = 'url_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    event = Column(String)
    event_date = Column(Date)
    url = Column(String)
    url_hash = Column(String)
    category = Column(String) # "agenda" or "minutes"
    created_at = Column(DateTime, default=datetime.datetime.now)


class EventStage(Base):
    """
    A temporary staging area where the crawler saves meeting details.
    These are later "promoted" to the main Event table after checking for duplicates.
    """
    __tablename__ = 'event_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    name = Column(String) # e.g. "City Council Regular Meeting"
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date) # Date of the meeting
    source = Column(String)
    source_url = Column(String)
    meeting_type = Column(String)

