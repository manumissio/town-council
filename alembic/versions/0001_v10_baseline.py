"""Create the immutable Town Council v10 PostgreSQL baseline."""

from __future__ import annotations

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision: str = "0001_v10_baseline"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

BASELINE_DOWNGRADE_ERROR = (
    "The v10 baseline is the migration floor and cannot be downgraded."
)
VECTOR_EXTENSION_DDL = sa.DDL("CREATE EXTENSION IF NOT EXISTS vector")
CURRENT_TIMESTAMP_DEFAULT = sa.text("now()")
MENTIONED_PERSON_DEFAULT = sa.text("'mentioned'")


def upgrade() -> None:
    """Create the complete v10 schema without importing mutable ORM metadata."""
    op.execute(VECTOR_EXTENSION_DDL)

    op.create_table(
        "catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("extraction_status", sa.String(length=20), nullable=True),
        sa.Column(
            "extraction_attempted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("extraction_attempt_count", sa.Integer(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_source_hash", sa.String(length=64), nullable=True),
        sa.Column("summary_extractive", sa.Text(), nullable=True),
        sa.Column("agenda_items_hash", sa.String(length=64), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("entities_source_hash", sa.String(length=64), nullable=True),
        sa.Column("tables", sa.JSON(), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=True),
        sa.Column("topics_source_hash", sa.String(length=64), nullable=True),
        sa.Column("related_ids", sa.JSON(), nullable=True),
        sa.Column("lineage_id", sa.String(length=64), nullable=True),
        sa.Column("lineage_confidence", sa.Float(), nullable=True),
        sa.Column("lineage_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "agenda_segmentation_status",
            sa.String(length=20),
            nullable=True,
        ),
        sa.Column(
            "agenda_segmentation_attempted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "agenda_segmentation_item_count",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("agenda_segmentation_error", sa.Text(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="catalog_pkey"),
        sa.UniqueConstraint("url_hash", name="catalog_url_hash_key"),
    )
    op.create_index(
        "idx_catalog_hash",
        "catalog",
        ["url_hash"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_extraction_attempted_at",
        "catalog",
        ["extraction_attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_extraction_status",
        "catalog",
        ["extraction_status"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_lineage_confidence",
        "catalog",
        ["lineage_confidence"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_lineage_id",
        "catalog",
        ["lineage_id"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_agenda_segmentation_attempted_at",
        "catalog",
        ["agenda_segmentation_attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_agenda_segmentation_status",
        "catalog",
        ["agenda_segmentation_status"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_lineage_updated_at",
        "catalog",
        ["lineage_updated_at"],
        unique=False,
    )

    op.create_table(
        "event_stage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ocd_division_id", sa.String(length=255), nullable=True),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "scraped_datetime",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("meeting_type", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id", name="event_stage_pkey"),
    )

    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ocd_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("biography", sa.String(length=5000), nullable=True),
        sa.Column("current_role", sa.String(length=255), nullable=True),
        sa.Column(
            "is_elected",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=True,
        ),
        sa.Column(
            "person_type",
            sa.String(length=20),
            server_default=MENTIONED_PERSON_DEFAULT,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="person_pkey"),
    )
    op.create_index(
        "ix_person_is_elected",
        "person",
        ["is_elected"],
        unique=False,
    )
    op.create_index("ix_person_name", "person", ["name"], unique=False)
    op.create_index("ix_person_ocd_id", "person", ["ocd_id"], unique=True)
    op.create_index(
        "ix_person_person_type",
        "person",
        ["person_type"],
        unique=False,
    )

    op.create_table(
        "place",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type_", sa.String(length=50), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("ocd_division_id", sa.String(length=255), nullable=False),
        sa.Column("seed_url", sa.String(length=500), nullable=True),
        sa.Column("hosting_service", sa.String(length=100), nullable=True),
        sa.Column("crawler", sa.Boolean(), nullable=True),
        sa.Column("crawler_name", sa.String(length=100), nullable=True),
        sa.Column("crawler_type", sa.String(length=50), nullable=True),
        sa.Column("crawler_owner", sa.String(length=100), nullable=True),
        sa.Column("legistar_client", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id", name="place_pkey"),
    )
    op.create_index(
        "ix_place_ocd_division_id",
        "place",
        ["ocd_division_id"],
        unique=True,
    )

    op.create_table(
        "url_stage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ocd_division_id", sa.String(length=255), nullable=True),
        sa.Column("event", sa.String(length=255), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("url_hash", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="url_stage_pkey"),
    )

    op.create_table(
        "url_stage_hist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ocd_division_id", sa.String(length=255), nullable=True),
        sa.Column("event", sa.String(length=255), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("url_hash", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="url_stage_hist_pkey"),
    )

    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ocd_id", sa.String(length=255), nullable=True),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("classification", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["place.id"],
            name="organization_place_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="organization_pkey"),
    )
    op.create_index(
        "ix_organization_ocd_id",
        "organization",
        ["ocd_id"],
        unique=True,
    )
    op.create_index(
        "ix_organization_place_id",
        "organization",
        ["place_id"],
        unique=False,
    )

    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ocd_id", sa.String(length=255), nullable=True),
        sa.Column("ocd_division_id", sa.String(length=255), nullable=True),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "scraped_datetime",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("meeting_type", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="event_organization_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["place.id"],
            name="event_place_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="event_pkey"),
    )
    op.create_index(
        "idx_event_date_place",
        "event",
        ["record_date", "place_id"],
        unique=False,
    )
    op.create_index(
        "idx_event_org",
        "event",
        ["organization_id", "record_date"],
        unique=False,
    )
    op.create_index("ix_event_ocd_id", "event", ["ocd_id"], unique=True)
    op.create_index(
        "ix_event_organization_id",
        "event",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "membership",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="membership_organization_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["person.id"],
            name="membership_person_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="membership_pkey"),
    )
    op.create_index(
        "ix_membership_organization_id",
        "membership",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_membership_person_id",
        "membership",
        ["person_id"],
        unique=False,
    )

    op.create_table(
        "agenda_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ocd_id", sa.String(length=255), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(length=100), nullable=True),
        sa.Column("result", sa.String(length=100), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text_offset", sa.Integer(), nullable=True),
        sa.Column("votes", sa.JSON(), nullable=True),
        sa.Column("raw_history", sa.Text(), nullable=True),
        sa.Column("legistar_matter_id", sa.Integer(), nullable=True),
        sa.Column("spatial_coords", sa.JSON(), nullable=True),
        sa.Column("catalog_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["catalog.id"],
            name="agenda_item_catalog_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event.id"],
            name="agenda_item_event_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="agenda_item_pkey"),
    )
    op.create_index(
        "ix_agenda_item_event_id",
        "agenda_item",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        "ix_agenda_item_legistar_matter_id",
        "agenda_item",
        ["legistar_matter_id"],
        unique=False,
    )
    op.create_index(
        "ix_agenda_item_ocd_id",
        "agenda_item",
        ["ocd_id"],
        unique=True,
    )

    op.create_table(
        "data_issue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event.id"],
            name="data_issue_event_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="data_issue_pkey"),
    )
    op.create_index(
        "ix_data_issue_event_id",
        "data_issue",
        ["event_id"],
        unique=False,
    )

    op.create_table(
        "document",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("catalog_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("url_hash", sa.String(length=64), nullable=True),
        sa.Column("media_type", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["catalog.id"],
            name="document_catalog_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event.id"],
            name="document_event_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["place.id"],
            name="document_place_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="document_pkey"),
    )
    op.create_index(
        "idx_doc_catalog",
        "document",
        ["catalog_id"],
        unique=False,
    )
    op.create_index(
        "idx_doc_category",
        "document",
        ["category", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_doc_place_event",
        "document",
        ["place_id", "event_id"],
        unique=False,
    )

    op.create_table(
        "semantic_embedding",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_id", sa.Integer(), nullable=True),
        sa.Column("agenda_item_id", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=CURRENT_TIMESTAMP_DEFAULT,
            nullable=True,
        ),
        sa.CheckConstraint(
            "(catalog_id IS NOT NULL AND agenda_item_id IS NULL) OR "
            "(catalog_id IS NULL AND agenda_item_id IS NOT NULL)",
            name="check_single_entity_reference",
        ),
        sa.ForeignKeyConstraint(
            ["agenda_item_id"],
            ["agenda_item.id"],
            name="semantic_embedding_agenda_item_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["catalog.id"],
            name="semantic_embedding_catalog_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="semantic_embedding_pkey"),
    )
    op.create_index(
        "ix_semantic_embedding_catalog_model",
        "semantic_embedding",
        ["catalog_id", "model_name"],
        unique=True,
    )
    op.create_index(
        "ix_semantic_embedding_item_model",
        "semantic_embedding",
        ["agenda_item_id", "model_name"],
        unique=True,
    )
    op.create_index(
        "ix_semantic_embedding_hnsw",
        "semantic_embedding",
        ["embedding"],
        unique=False,
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_using="hnsw",
        postgresql_where=sa.text("embedding IS NOT NULL"),
    )


def downgrade() -> None:
    """Prevent destructive rollback below the adopted migration floor."""
    raise RuntimeError(BASELINE_DOWNGRADE_ERROR)
