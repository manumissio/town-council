from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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
    legistar_body_id = Column(Integer, nullable=True)
    legistar_body_guid = Column(String(36), nullable=True)
    roster_source_url = Column(String(500), nullable=True)
    roster_synced_at = Column(DateTime(timezone=True), nullable=True)

    place = relationship("Place", back_populates="organizations")
    events = relationship("Event", back_populates="organization")
    memberships = relationship("Membership", back_populates="organization")

    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "legistar_body_id",
            name="uq_organization_place_legistar_body",
        ),
    )


class Person(Base):
    __tablename__ = "person"

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    legistar_client = Column(String(100), nullable=False)
    legistar_person_id = Column(Integer, nullable=False)
    roster_source_url = Column(String(500), nullable=False)
    roster_synced_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("Membership", back_populates="person")

    __table_args__ = (
        UniqueConstraint(
            "legistar_client",
            "legistar_person_id",
            name="uq_person_legistar_identity",
        ),
    )


class Membership(Base):
    __tablename__ = "membership"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organization.id"),
        nullable=False,
        index=True,
    )
    label = Column(String(255))
    role = Column(String(100), default="member")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    legistar_client = Column(String(100), nullable=False)
    legistar_office_record_id = Column(Integer, nullable=False)
    legistar_office_record_guid = Column(String(36), nullable=False)
    roster_source_url = Column(String(500), nullable=False)
    roster_last_modified_at = Column(DateTime(timezone=True), nullable=False)
    roster_synced_at = Column(DateTime(timezone=True), nullable=False)

    person = relationship("Person", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint(
            "legistar_client",
            "legistar_office_record_id",
            name="uq_membership_legistar_identity",
        ),
    )
