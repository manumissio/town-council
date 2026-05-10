from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from pipeline.model_base import Base, VECTOR_COLUMN_TYPE


class AgendaItem(Base):
    __tablename__ = "agenda_item"

    id = Column(Integer, primary_key=True)
    ocd_id = Column(String(255), unique=True, index=True)
    event_id = Column(Integer, ForeignKey("event.id"), nullable=False, index=True)

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

    catalog_id = Column(Integer, ForeignKey("catalog.id"), nullable=True)

    event = relationship("Event", back_populates="agenda_items")
    catalog = relationship("Catalog", back_populates="agenda_items")
    semantic_embeddings = relationship("SemanticEmbedding", back_populates="agenda_item", cascade="all, delete-orphan")


class SemanticEmbedding(Base):
    __tablename__ = "semantic_embedding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_id = Column(Integer, ForeignKey("catalog.id", ondelete="CASCADE"), nullable=True)
    agenda_item_id = Column(Integer, ForeignKey("agenda_item.id", ondelete="CASCADE"), nullable=True)
    model_name = Column(String(120), nullable=False, default="all-MiniLM-L6-v2")
    embedding_dim = Column(Integer, nullable=False, default=384)
    embedding: object = Column(VECTOR_COLUMN_TYPE(384), nullable=True)
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


class Catalog(Base):
    __tablename__ = "catalog"

    id = Column(Integer, primary_key=True)
    url = Column(String(500))
    url_hash = Column(String(64), unique=True, nullable=False)
    location = Column(String(500))
    filename = Column(String(255))

    content = Column(Text)
    # Hash of extracted `content` (normalized). Used to detect when derived fields
    # like summaries/topics are stale after re-extraction.
    content_hash = Column(String(64), nullable=True)
    extraction_status = Column(String(20), nullable=True)
    extraction_attempted_at = Column(DateTime, nullable=True)
    extraction_attempt_count = Column(Integer, nullable=True)
    extraction_error = Column(Text, nullable=True)
    summary = Column(Text)
    # Hash of the input version that `summary` was generated from. For text-grounded
    # summaries this is `content_hash`; for deterministic agenda summaries it is the
    # structured agenda fingerprint (`agenda_items_hash`).
    summary_source_hash = Column(String(64), nullable=True)
    summary_extractive = Column(Text)
    # Hash of the substantive agenda-item payload for this catalog. Agenda summaries
    # use this instead of `content_hash` because they are derived from structured rows.
    agenda_items_hash = Column(String(64), nullable=True)

    entities = Column(JSON, nullable=True)
    # Hash of the `content` version that `entities` were generated from.
    entities_source_hash = Column(String(64), nullable=True)
    tables = Column(JSON, nullable=True)
    topics = Column(JSON, nullable=True)
    # Hash of the `content` version that `topics` were generated from.
    topics_source_hash = Column(String(64), nullable=True)
    related_ids = Column(JSON, nullable=True)
    lineage_id = Column(String(64), nullable=True, index=True)
    lineage_confidence = Column(Float, nullable=True, index=True)
    lineage_updated_at = Column(DateTime, nullable=True)

    # Agenda segmentation status prevents poison-pill reprocessing when a document genuinely yields 0 items.
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
        Index("idx_catalog_hash", "url_hash"),
        Index("ix_catalog_extraction_status", "extraction_status"),
        Index("ix_catalog_extraction_attempted_at", "extraction_attempted_at"),
    )


class Document(Base):
    __tablename__ = "document"

    id = Column(Integer, primary_key=True)
    place_id = Column(Integer, ForeignKey("place.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("event.id"), nullable=False)
    catalog_id = Column(Integer, ForeignKey("catalog.id"), nullable=True)
    url = Column(String(500))
    url_hash = Column(String(64))
    media_type = Column(String(100))
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)
    page_count = Column(Integer)

    place = relationship("Place")
    event = relationship("Event", back_populates="documents")
    catalog = relationship("Catalog", back_populates="document")

    __table_args__ = (
        Index("idx_doc_place_event", "place_id", "event_id"),
        Index("idx_doc_category", "category", "created_at"),
        Index("idx_doc_catalog", "catalog_id"),
    )
