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
    """
    Base.metadata.create_all(engine)


class Place(Base):
    """
    Represents a Jurisdiction (City or Town, e.g., "Belmont, CA").
    
    Security Fix: Added UniqueConstraint on ocd_division_id to prevent 
    duplicate city entries in the database.
    """
    __tablename__ = 'place'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type_ = Column(String)
    state = Column(String, nullable=False)
    country = Column(String, default="us")
    display_name = Column(String)
    ocd_division_id = Column(String, unique=True, index=True, nullable=False)
    seed_url = Column(String)
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
    ocd_id = Column(String, unique=True, index=True) # e.g. ocd-organization/uuid
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False, index=True)
    name = Column(String, nullable=False) # e.g. "Planning Commission"
    classification = Column(String) # e.g. "legislature", "committee"
    
    # Relationships
    place = relationship("Place", back_populates="organizations")
    events = relationship("Event", back_populates="organization")
    memberships = relationship("Membership", back_populates="organization")


class Person(Base):
    """
    Represents an Individual (e.g., an elected official or staff member).
    
    Why this is needed:
    To track accountability, we need to move from simple text names 
    to unique 'Person' records that can be tracked across multiple years and cities.
    """
    __tablename__ = 'person'

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String, unique=True, index=True) # e.g. ocd-person/uuid
    name = Column(String, nullable=False, index=True)
    image_url = Column(String, nullable=True)
    biography = Column(String, nullable=True)
    current_role = Column(String, nullable=True)
    
    # Metadata for disambiguation
    created_at = Column(DateTime, default=datetime.datetime.now)

    # Relationships
    memberships = relationship("Membership", back_populates="person")


class Membership(Base):
    """
    A 'Bridge' table that links a Person to an Organization.
    
    Why this is needed:
    In the OCD standard, we don't just say 'John is a person'. 
    We track that 'John' is a 'Member' of the 'City Council'.
    """
    __tablename__ = 'membership'

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey('person.id'), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    # Role details
    label = Column(String) # e.g. "Chair", "Member", "Mayor"
    role = Column(String, default="member")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Relationships
    person = relationship("Person", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")


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
    ocd_id = Column(String, unique=True, index=True) # e.g. ocd-event/uuid
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
    agenda_items = relationship('AgendaItem', back_populates='event', cascade="all, delete-orphan")


class AgendaItem(Base):
    """
    Represents a single segment or item from a meeting agenda.
    
    Why this is needed:
    Meeting minutes are often huge. By splitting them into individual items,
    we can take a user directly to the relevant part of a 100-page document.
    """
    __tablename__ = 'agenda_item'

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String, unique=True, index=True) # e.g. ocd-agendaitem/uuid
    event_id = Column(Integer, ForeignKey('event.id'), nullable=False, index=True)
    
    # Content extracted by AI
    order = Column(Integer) # The 1st, 2nd, 3rd item in the agenda
    title = Column(String, nullable=False)
    description = Column(String)
    classification = Column(String) # e.g. "Action", "Discussion", "Consent"
    result = Column(String) # e.g. "Passed", "Failed", "Deferred"
    
    # Link back to the raw text source
    catalog_id = Column(Integer, ForeignKey('catalog.id'), nullable=True)

    # Relationships
    event = relationship('Event', back_populates='agenda_items')
    catalog = relationship('Catalog')


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
    
    # AI-generated 3-bullet summary (Generative - Gemini)
    summary = Column(String, nullable=True)

    # Local zero-cost summary (Extractive - TextRank)
    summary_extractive = Column(String, nullable=True)
    
    # Names of People, Orgs, and Places found in the text (JSON)
    # Format: {"orgs": ["Police Dept"], "locs": ["Main St"], "persons": ["Mayor Smith"]}
    entities = Column(JSON, nullable=True)
    
    # Structured data tables extracted from the PDF (JSON)
    tables = Column(JSON, nullable=True)
    
    # AI-discovered topics/themes (e.g. ["Housing", "Zoning"]) (JSON)
    topics = Column(JSON, nullable=True)

    # Pre-calculated references to similar meetings (JSON list of Catalog IDs)
    related_ids = Column(JSON, nullable=True)
    
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
