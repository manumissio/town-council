import datetime
import os

from sqlalchemy import create_engine
from sqlalchemy import Column, Boolean, String, Integer, Date, DateTime, JSON
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.schema import Index

# Modern SQLAlchemy 2.0 style: Subclassing DeclarativeBase instead of calling a function.
# This makes the code more robust and compatible with modern Python tools.
class Base(DeclarativeBase):
    pass


def db_connect():
    """
    Connects to the database (PostgreSQL in production, SQLite for local testing).
    
    Why this is needed:
    It handles the secure connection details and ensures we can talk to the database.
    It automatically switches between 'real' database mode (Docker) and 'test' mode.
    """
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Use PostgreSQL with connection pooling for high performance.
        # This keeps a few connections open and ready so we don't have to reconnect every time.
        return create_engine(
            database_url,
            pool_size=10,         # Maintain 10 open connections
            max_overflow=20,      # Allow up to 20 extra connections if busy
            pool_timeout=30,      # Wait 30s for a connection before giving up
            pool_recycle=1800     # Refresh connections every 30 mins to keep them healthy
        )
    else:
        # Fallback to a local SQLite file for simple testing without Docker.
        # This makes it easy to run scripts on your own laptop.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        db_path = os.path.join(project_root, 'test_db.sqlite')
        print("WARNING: DATABASE_URL not set. Using local SQLite.")
        return create_engine(f'sqlite:///{db_path}')


def create_tables(engine):
    """
    Creates all the tables defined below if they don't already exist.
    Also creates an index on the city ID to make lookups faster.
    """
    Index("place_ocd_id_idx", Place.ocd_division_id)
    Base.metadata.create_all(engine)


class Place(Base):
    """
    Represents a Jurisdiction (City or Town, e.g., "Belmont, CA").
    Stores metadata like the city name, state, and where to find its meetings.
    """
    __tablename__ = 'place'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    type_ = Column(String)
    state = Column(String)
    country = Column(String)
    display_name = Column(String) # e.g. "Belmont, CA"
    ocd_division_id = Column(String, index=True) # Unique ID for the city
    seed_url = Column(String) # The main URL for the city council's website
    hosting_service = Column(String) # Does it use Granicus, Legistar, etc?
    crawler = Column(Boolean, default=False)
    crawler_name = Column(String)
    crawler_type = Column(String)
    crawler_owner = Column(String)

    # Relationship to organizations within this city
    organizations = relationship("Organization", back_populates="place")


class Organization(Base):
    """
    Represents a Legislative Body or Committee (e.g., "City Council" or "Planning Commission").
    
    Why this is needed:
    Following the Open Civic Data (OCD) standard, we need to distinguish 
    which specific group within a city held a meeting.
    """
    __tablename__ = 'organization'

    id = Column(Integer, primary_key=True)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False, index=True)
    name = Column(String, nullable=False) # e.g. "Planning Commission"
    classification = Column(String) # e.g. "legislature", "committee"
    
    # Relationships
    place = relationship("Place", back_populates="organizations")
    events = relationship("Event", back_populates="organization")


class UrlStage(Base):
    """
    A temporary staging area for URLs found by the crawler.
    The downloader reads from here to know what files to fetch.
    """
    __tablename__ = 'url_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    event = Column(String)
    event_date = Column(Date)
    url = Column(String) # The direct link to the PDF
    url_hash = Column(String) # Unique fingerprint of the URL
    category = Column(String) # "agenda" or "minutes"
    created_at = Column(DateTime, default=datetime.datetime.now)


class EventStage(Base):
    """
    A temporary staging area for meeting events found by the crawler.
    Used to check for duplicates before adding to the main Event table.
    """
    __tablename__ = 'event_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    organization_name = Column(String) # The name of the body (e.g. "City Council")
    name = Column(String) # e.g. "City Council Regular Meeting"
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date) # When the meeting happened
    source = Column(String)
    source_url = Column(String)
    meeting_type = Column(String)


class Event(Base):
    """
    Represents a specific Meeting held by an Organization.
    
    Why this is needed:
    It links a specific City group (Organization) to a Date and a Name.
    """
    __tablename__ = 'event'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=True, index=True)
    name = Column(String)
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date)
    source = Column(String)
    source_url = Column(String)
    meeting_type = Column(String)

    # Relationships
    place = relationship('Place')
    organization = relationship('Organization', back_populates='events')


class UrlStageHist(Base):
    """
    History log of all URLs we have ever processed.
    Keeps the main staging table clean and small.
    """
    __tablename__ = 'url_stage_hist'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    event = Column(String)
    event_date = Column(Date)
    url = Column(String)
    url_hash = Column(String)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)


class Catalog(Base):
    """
    The main library of all downloaded files.
    Stores the file path, raw text content, and AI-generated metadata.
    """
    __tablename__ = 'catalog'

    id = Column(Integer, primary_key=True)
    url = Column(String)
    url_hash = Column(String, unique=True, index=True)
    location = Column(String) # Local file path (e.g., data/us/ca/belmont/hash.pdf)
    filename = Column(String)
    
    # The full text extracted from the PDF (OCR)
    content = Column(String, nullable=True)
    
    # AI-generated 3-bullet summary
    summary = Column(String, nullable=True)
    
    # Names of People, Orgs, and Places found in the text (JSON)
    # Format: {"orgs": ["Police Dept"], "locs": ["Main St"], "persons": ["Mayor Smith"]}
    entities = Column(JSON, nullable=True)
    
    # Structured data tables extracted from the PDF (JSON)
    tables = Column(JSON, nullable=True)
    
    # AI-discovered topics/themes (e.g. ["Housing", "Zoning"]) (JSON)
    topics = Column(JSON, nullable=True)
    
    uploaded_at = Column(DateTime, default=datetime.datetime.now)


class Document(Base):
    """
    Links a File (Catalog) to a Meeting (Event).
    Allows us to say "This PDF belongs to the meeting on Feb 10th".
    """
    __tablename__ = 'document'

    id = Column(Integer, primary_key=True)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey('event.id'), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey('catalog.id'), nullable=True, index=True)
    url = Column(String)
    url_hash = Column(String)
    media_type = Column(String)
    category = Column(String) # "agenda" or "minutes"
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # Relationships allow us to easily access related data in code
    place = relationship('Place')
    event = relationship('Event')
    catalog = relationship('Catalog')


engine = db_connect()
create_tables(engine)
