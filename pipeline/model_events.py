from __future__ import annotations

import datetime
import enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from pipeline.model_base import Base


class IssueType(enum.Enum):
    """
    Standardized types of data problems a user can report.
    Using an Enum prevents 'typos' and ensures data consistency.
    """

    BROKEN_LINK = "broken_link"  # The PDF link gives a 404 error
    GARBLED_TEXT = "garbled_text"  # OCR failed and text is unreadable
    WRONG_CITY = "wrong_city"  # Meeting is assigned to the wrong town
    OTHER = "other"  # Catch-all for unique issues


class DataIssue(Base):
    __tablename__ = "data_issue"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("event.id"), index=True, nullable=False)
    issue_type = Column(String(50), nullable=False)
    description = Column(String(500))
    status = Column(String(20), default="open")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    event = relationship("Event")


class UrlStage(Base):
    __tablename__ = "url_stage"

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String(255))
    event = Column(String(255))
    event_date = Column(Date)
    url = Column(String(500))
    url_hash = Column(String(64))
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)


class EventStage(Base):
    __tablename__ = "event_stage"

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
    __tablename__ = "event"

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    ocd_division_id = Column(String(255))
    place_id = Column(Integer, ForeignKey("place.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=True, index=True)
    name = Column(String(255))
    scraped_datetime = Column(DateTime, default=datetime.datetime.now)
    record_date = Column(Date)
    source = Column(String(500))
    source_url = Column(String(500))
    meeting_type = Column(String(100))

    place = relationship("Place")
    organization = relationship("Organization", back_populates="events")
    documents = relationship("Document", back_populates="event", cascade="all, delete-orphan")
    agenda_items = relationship("AgendaItem", back_populates="event", cascade="all, delete-orphan")
    data_issues = relationship("DataIssue", back_populates="event")

    __table_args__ = (
        Index("idx_event_date_place", "record_date", "place_id"),
        Index("idx_event_org", "organization_id", "record_date"),
    )


class UrlStageHist(Base):
    __tablename__ = "url_stage_hist"

    id = Column(Integer, primary_key=True)
    ocd_division_id = Column(String(255))
    event = Column(String(255))
    event_date = Column(Date)
    url = Column(String(500))
    url_hash = Column(String(64))
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)
