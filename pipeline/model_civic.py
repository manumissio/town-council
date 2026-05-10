from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from pipeline.model_base import Base


class Place(Base):
    __tablename__ = "place"

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
    __tablename__ = "organization"

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    place_id = Column(Integer, ForeignKey("place.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    classification = Column(String(100))

    place = relationship("Place", back_populates="organizations")
    events = relationship("Event", back_populates="organization")
    memberships = relationship("Membership", back_populates="organization")


class Person(Base):
    __tablename__ = "person"

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
    __tablename__ = "membership"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    label = Column(String(255))
    role = Column(String(100), default="member")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    person = relationship("Person", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")
