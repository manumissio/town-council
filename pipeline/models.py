import datetime
import os

from sqlalchemy import create_engine
from sqlalchemy import Column, Boolean, String, Integer, Date, DateTime, JSON
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Index

DeclarativeBase = declarative_base()


def db_connect():
    """
    Connect to the database using the DATABASE_URL environment variable.
    Defaults to a local SQLite file if the variable is not set.
    """
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Use PostgreSQL with connection pooling for performance
        return create_engine(
            database_url,
            pool_size=10,         # Maintain 10 open connections
            max_overflow=20,      # Allow up to 20 overflow connections
            pool_timeout=30,      # Wait 30s for a connection before failing
            pool_recycle=1800     # Recycle connections every 30 mins
        )
    else:
        # Fallback to local SQLite for manual testing without Docker
        # Get the directory of the current file (town-council/pipeline/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Project root is one level up (town-council/)
        project_root = os.path.dirname(current_dir)
        db_path = os.path.join(project_root, 'test_db.sqlite')
        print("WARNING: DATABASE_URL not set. Using local SQLite.")
        return create_engine(f'sqlite:///{db_path}')


def create_tables(engine):
    Index("place_ocd_id_idx", Place.ocd_division_id)
    DeclarativeBase.metadata.create_all(engine)


class Place(DeclarativeBase):
    """Place table"""
    __tablename__ = 'place'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    type_ = Column(String)
    state = Column(String)
    country = Column(String)
    display_name = Column(String)
    ocd_division_id = Column(String, index=True)
    seed_url = Column(String)
    hosting_service = Column(String)
    crawler = Column(Boolean, default=False)
    craler_name = Column(String)
    crawler_type = Column(String)
    crawler_owner = Column(String)


class UrlStage(DeclarativeBase):
    """Url Staging Table"""
    __tablename__ = 'url_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    event = Column(String)
    event_date = Column(Date)
    url = Column(String)
    url_hash = Column(String)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)


class EventStage(DeclarativeBase):
    """Event table"""
    __tablename__ = 'event_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    name = Column(String)
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date)
    source = Column(String)
    source_url = Column(String)
    meeting_type = Column(String)


#####

class Event(DeclarativeBase):
    """Event table"""
    __tablename__ = 'event'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False)
    name = Column(String)
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date)
    source = Column(String)
    source_url = Column(String)
    meeting_type = Column(String)


class UrlStageHist(DeclarativeBase):
    """Url Staging History Table"""
    __tablename__ = 'url_stage_hist'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String)
    event = Column(String)
    event_date = Column(Date)
    url = Column(String)
    url_hash = Column(String)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)


class Catalog(DeclarativeBase):
    """Document catalog table"""
    __tablename__ = 'catalog'

    id = Column(Integer, primary_key=True)
    url = Column(String)
    url_hash = Column(String, unique=True, index=True)
    location = Column(String)
    filename = Column(String)
    # Extracted text content from the document
    content = Column(String, nullable=True)
    # AI-generated summary of the content
    summary = Column(String, nullable=True)
    # NLP-extracted entities (Organizations, Locations, etc.)
    # Stored as JSON: {"orgs": [], "locs": [], "persons": []}
    entities = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.now)


class Document(DeclarativeBase):
    """Document table"""
    __tablename__ = 'document'

    id = Column(Integer, primary_key=True)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey('event.id'), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey('catalog.id'), nullable=True, index=True)
    url = Column(String)
    url_hash = Column(String)
    media_type = Column(String)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)
    place = relationship('Place')
    event = relationship('Event')
    catalog = relationship('Catalog')


engine = db_connect()
create_tables(engine)
