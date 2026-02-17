import datetime
import os
import json

from sqlalchemy import create_engine, func
from sqlalchemy import Column, Boolean, String, Integer, Date, DateTime, JSON, Text, CheckConstraint, Float
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.schema import Index
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    class Vector(TypeDecorator):
        """
        Lightweight fallback so local imports/tests do not crash when pgvector is absent.
        """

        impl = Text
        cache_ok = True

        def __init__(self, *args, **kwargs):
            super().__init__()

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return json.dumps(list(value))
            return str(value)

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return value

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
    
    if database_url and database_url.startswith('postgresql'):
        # Use PostgreSQL with connection pooling for high performance.
        return create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800
        )
    elif database_url:
        # Custom URL (e.g. sqlite)
        return create_engine(database_url)
    else:
        # Fallback to a local SQLite file

        # This makes it easy to run scripts on your own laptop.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        db_path = os.path.join(project_root, 'test_db.sqlite')
        print("WARNING: DATABASE_URL not set. Using local SQLite.")
        return create_engine(f'sqlite:///{db_path}')


def create_tables(engine):
    """
    Creates all the tables defined below if they't already exist.
    """
    Base.metadata.create_all(engine)

# Removed: create_tables(engine) from global scope to avoid import-side effects



import enum

class IssueType(enum.Enum):
    """
    Standardized types of data problems a user can report.
    Using an Enum prevents 'typos' and ensures data consistency.
    """
    BROKEN_LINK = "broken_link"      # The PDF link gives a 404 error
    GARBLED_TEXT = "garbled_text"    # OCR failed and text is unreadable
    WRONG_CITY = "wrong_city"        # Meeting is assigned to the wrong town
    OTHER = "other"                  # Catch-all for unique issues

class DataIssue(Base):
    __tablename__ = 'data_issue'

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey('event.id'), index=True, nullable=False)
    issue_type = Column(String(50), nullable=False)
    description = Column(String(500))
    status = Column(String(20), default="open")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    event = relationship("Event")

class Place(Base):
    __tablename__ = 'place'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    type_ = Column(String(50))
    state = Column(String(2), nullable=False)
    country = Column(String(2), default="us")
    display_name = Column(String(255))
    ocd_division_id = Column(String(255), unique=True, index=True, nullable=False)
    seed_url = Column(String(500))
    hosting_service = Column(String(100))
    crawler = Column(Boolean, default=False)
    crawler_name = Column(String(100))
    crawler_type = Column(String(50))
    crawler_owner = Column(String(100))
    legistar_client = Column(String(100), nullable=True)

    organizations = relationship("Organization", back_populates="place")


class Organization(Base):
    __tablename__ = 'organization'

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    classification = Column(String(100))
    
    place = relationship("Place", back_populates="organizations")
    events = relationship("Event", back_populates="organization")
    memberships = relationship("Membership", back_populates="organization")


class Person(Base):
    __tablename__ = 'person'

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    image_url = Column(String(500), nullable=True)
    biography = Column(String(5000), nullable=True)
    current_role = Column(String(255), nullable=True)
    is_elected = Column(Boolean, default=False, index=True)
    # Distinguishes official records from mention-only NLP detections.
    person_type = Column(String(20), default="mentioned", index=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.now)

    memberships = relationship("Membership", back_populates="person")


class Membership(Base):
    __tablename__ = 'membership'

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey('person.id'), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    label = Column(String(255))
    role = Column(String(100), default="member")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    person = relationship("Person", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")


class UrlStage(Base):
    __tablename__ = 'url_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String(255))
    event = Column(String(255))
    event_date = Column(Date)
    url = Column(String(500))
    url_hash = Column(String(64))
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)


class EventStage(Base):
    __tablename__ = 'event_stage'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String(255))
    organization_name = Column(String(255))
    name = Column(String(255))
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date)
    source = Column(String(500))
    source_url = Column(String(500))
    meeting_type = Column(String(100))


class Event(Base):
    __tablename__ = 'event'

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    ocd_division_id = Column(String(255))
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=True, index=True)
    name = Column(String(255))
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date)
    source = Column(String(500))
    source_url = Column(String(500))
    meeting_type = Column(String(100))

    place = relationship('Place')
    organization = relationship('Organization', back_populates='events')
    documents = relationship("Document", back_populates="event", cascade="all, delete-orphan")
    agenda_items = relationship('AgendaItem', back_populates='event', cascade="all, delete-orphan")
    data_issues = relationship('DataIssue', back_populates='event')

    __table_args__ = (
        Index('idx_event_date_place', 'record_date', 'place_id'),
        Index('idx_event_org', 'organization_id', 'record_date'),
    )


class AgendaItem(Base):
    __tablename__ = 'agenda_item'

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    event_id = Column(Integer, ForeignKey('event.id'), nullable=False, index=True)
    
    order = Column(Integer)
    title = Column(String(1000), nullable=False)
    description = Column(Text)
    classification = Column(String(100))
    result = Column(String(100))
    
    page_number = Column(Integer, nullable=True)
    text_offset = Column(Integer, nullable=True)
    
    # Ground Truth fields for verification
    votes = Column(JSON, nullable=True)
    raw_history = Column(Text, nullable=True)
    legistar_matter_id = Column(Integer, nullable=True, index=True)
    spatial_coords = Column(JSON, nullable=True)
    
    catalog_id = Column(Integer, ForeignKey('catalog.id'), nullable=True)

    event = relationship('Event', back_populates='agenda_items')
    catalog = relationship('Catalog', back_populates='agenda_items')
    semantic_embeddings = relationship("SemanticEmbedding", back_populates="agenda_item", cascade="all, delete-orphan")


class SemanticEmbedding(Base):
    __tablename__ = "semantic_embedding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_id = Column(Integer, ForeignKey("catalog.id", ondelete="CASCADE"), nullable=True)
    agenda_item_id = Column(Integer, ForeignKey("agenda_item.id", ondelete="CASCADE"), nullable=True)
    model_name = Column(String(120), nullable=False, default="all-MiniLM-L6-v2")
    embedding_dim = Column(Integer, nullable=False, default=384)
    embedding = Column(Vector(384), nullable=True)
    # Hash of the exact text payload used to create this vector.
    source_hash = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    catalog = relationship("Catalog", back_populates="semantic_embeddings")
    agenda_item = relationship("AgendaItem", back_populates="semantic_embeddings")

    __table_args__ = (
        CheckConstraint(
            "(catalog_id IS NOT NULL AND agenda_item_id IS NULL) OR "
            "(catalog_id IS NULL AND agenda_item_id IS NOT NULL)",
            name="check_single_entity_reference",
        ),
        Index("ix_semantic_embedding_catalog_model", "catalog_id", "model_name", unique=True),
        Index("ix_semantic_embedding_item_model", "agenda_item_id", "model_name", unique=True),
    )


class UrlStageHist(Base):
    __tablename__ = 'url_stage_hist'

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String(255))
    event = Column(String(255))
    event_date = Column(Date)
    url = Column(String(500))
    url_hash = Column(String(64))
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)


class Catalog(Base):
    __tablename__ = 'catalog'

    id = Column(Integer, primary_key=True)
    url = Column(String(500))
    url_hash = Column(String(64), unique=True, nullable=False)
    location = Column(String(500))
    filename = Column(String(255))
    
    content = Column(Text)
    # Hash of extracted `content` (normalized). Used to detect when derived fields
    # like summaries/topics are stale after re-extraction.
    content_hash = Column(String(64), nullable=True)
    summary = Column(Text)
    # Hash of the `content` version that `summary` was generated from.
    summary_source_hash = Column(String(64), nullable=True)
    summary_extractive = Column(Text)
    
    entities = Column(JSON, nullable=True)
    tables = Column(JSON, nullable=True)
    topics = Column(JSON, nullable=True)
    # Hash of the `content` version that `topics` were generated from.
    topics_source_hash = Column(String(64), nullable=True)
    related_ids = Column(JSON, nullable=True)
    lineage_id = Column(String(64), nullable=True, index=True)
    lineage_confidence = Column(Float, nullable=True, index=True)
    lineage_updated_at = Column(DateTime, nullable=True)

    # Agenda segmentation status for this catalog.
    # This prevents "poison pill" reprocessing when a document genuinely yields 0 items.
    agenda_segmentation_status = Column(String(20), nullable=True)  # complete|empty|failed
    agenda_segmentation_attempted_at = Column(DateTime, nullable=True)
    agenda_segmentation_item_count = Column(Integer, nullable=True)
    agenda_segmentation_error = Column(Text, nullable=True)
    
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    uploaded_at = Column(DateTime, default=datetime.datetime.now)

    document = relationship("Document", back_populates="catalog", uselist=False)
    agenda_items = relationship("AgendaItem", back_populates="catalog", cascade="all, delete-orphan")
    semantic_embeddings = relationship("SemanticEmbedding", back_populates="catalog", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_catalog_hash', 'url_hash'),
    )


class Document(Base):
    __tablename__ = 'document'

    id = Column(Integer, primary_key=True)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False)
    event_id = Column(Integer, ForeignKey('event.id'), nullable=False)
    catalog_id = Column(Integer, ForeignKey('catalog.id'), nullable=True)
    url = Column(String(500))
    url_hash = Column(String(64))
    media_type = Column(String(100))
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)
    page_count = Column(Integer)
    
    place = relationship('Place')
    event = relationship('Event', back_populates='documents')
    catalog = relationship('Catalog', back_populates='document')

    __table_args__ = (
        Index('idx_doc_place_event', 'place_id', 'event_id'),
        Index('idx_doc_category', 'category', 'created_at'),
        Index('idx_doc_catalog', 'catalog_id'),
    )


engine = db_connect()
# create_tables(engine) is removed to avoid import side-effects. 
# Use pipeline/db_init.py to create tables explicitly.
