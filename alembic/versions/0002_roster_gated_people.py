"""Replace document-derived people fields with authoritative roster identity."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "0002_roster_gated_people"
down_revision: str | None = "0001_v10_baseline"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

LEGACY_TABLE_LOCK = sa.text(
    "LOCK TABLE person, membership, catalog IN SHARE ROW EXCLUSIVE MODE"
)
PERSON_COUNT_QUERY = sa.text("SELECT count(*) FROM person")
MEMBERSHIP_COUNT_QUERY = sa.text("SELECT count(*) FROM membership")
PERSON_ENTITY_COUNT_QUERY = sa.text(
    """
    SELECT count(*)
    FROM catalog
    WHERE entities IS NOT NULL
      AND entities::jsonb ? 'persons'
    """
)
LEGACY_DATA_REMEDIATION_COMMAND = (
    "python scripts/remediate_legacy_people.py --apply"
)
ROSTER_DOWNGRADE_ERROR = (
    "The roster-gated schema is the current baseline and cannot be downgraded. "
    "Roll forward with current code or restore a verified backup in isolation."
)


def _legacy_person_counts(connection: Connection) -> tuple[int, int, int]:
    connection.execute(LEGACY_TABLE_LOCK)
    person_rows = int(connection.scalar(PERSON_COUNT_QUERY) or 0)
    membership_rows = int(connection.scalar(MEMBERSHIP_COUNT_QUERY) or 0)
    catalogs_with_person_entities = int(
        connection.scalar(PERSON_ENTITY_COUNT_QUERY) or 0
    )
    return person_rows, membership_rows, catalogs_with_person_entities


def _require_legacy_people_remediation(connection: Connection) -> None:
    person_rows, membership_rows, catalogs_with_person_entities = (
        _legacy_person_counts(connection)
    )
    if not any((person_rows, membership_rows, catalogs_with_person_entities)):
        return
    raise RuntimeError(
        "T-GOV-2A migration blocked: legacy person data remains. "
        f"person_rows={person_rows}, membership_rows={membership_rows}, "
        "catalogs_with_person_entities="
        f"{catalogs_with_person_entities}. "
        f"Back up the database, then run `{LEGACY_DATA_REMEDIATION_COMMAND}` "
        "before retrying the migration."
    )


def _add_organization_roster_columns() -> None:
    op.add_column(
        "organization",
        sa.Column("legistar_body_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "organization",
        sa.Column("legistar_body_guid", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "organization",
        sa.Column("roster_source_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "organization",
        sa.Column(
            "roster_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_organization_place_legistar_body",
        "organization",
        ["place_id", "legistar_body_id"],
    )


def _replace_person_identity_columns() -> None:
    op.drop_index("ix_person_is_elected", table_name="person")
    op.drop_index("ix_person_person_type", table_name="person")
    for legacy_column in (
        "image_url",
        "biography",
        "current_role",
        "is_elected",
        "person_type",
    ):
        op.drop_column("person", legacy_column)
    op.add_column(
        "person",
        sa.Column("legistar_client", sa.String(length=100), nullable=False),
    )
    op.add_column(
        "person",
        sa.Column("legistar_person_id", sa.Integer(), nullable=False),
    )
    op.add_column(
        "person",
        sa.Column(
            "roster_source_url",
            sa.String(length=500),
            nullable=False,
        ),
    )
    op.add_column(
        "person",
        sa.Column(
            "roster_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_person_legistar_identity",
        "person",
        ["legistar_client", "legistar_person_id"],
    )


def _add_membership_roster_columns() -> None:
    op.alter_column(
        "membership",
        "start_date",
        existing_type=sa.Date(),
        nullable=False,
    )
    op.add_column(
        "membership",
        sa.Column("legistar_client", sa.String(length=100), nullable=False),
    )
    op.add_column(
        "membership",
        sa.Column(
            "legistar_office_record_id",
            sa.Integer(),
            nullable=False,
        ),
    )
    op.add_column(
        "membership",
        sa.Column(
            "legistar_office_record_guid",
            sa.String(length=36),
            nullable=False,
        ),
    )
    op.add_column(
        "membership",
        sa.Column(
            "roster_source_url",
            sa.String(length=500),
            nullable=False,
        ),
    )
    op.add_column(
        "membership",
        sa.Column(
            "roster_last_modified_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.add_column(
        "membership",
        sa.Column(
            "roster_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_membership_legistar_identity",
        "membership",
        ["legistar_client", "legistar_office_record_id"],
    )


def upgrade() -> None:
    """Require cleanup, then establish authoritative roster identity."""
    _require_legacy_people_remediation(op.get_bind())
    _add_organization_roster_columns()
    _replace_person_identity_columns()
    _add_membership_roster_columns()


def downgrade() -> None:
    """Reject unsafe restoration of the document-derived people schema."""
    raise RuntimeError(ROSTER_DOWNGRADE_ERROR)
