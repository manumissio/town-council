from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
import importlib
from pathlib import Path
import sys
from types import ModuleType

import pytest
from sqlalchemy import Column
from sqlalchemy.sql.schema import DefaultClause
from sqlalchemy.sql.sqltypes import DateTime

CRAWLER_PROJECT_ROOT = Path(__file__).resolve().parents[1] / "council_crawler"
sys.path.insert(0, str(CRAWLER_PROJECT_ROOT))

from council_crawler import models as crawler_models
from pipeline.model_civic import Person
from pipeline.model_events import DataIssue, Event, EventStage, UrlStage, UrlStageHist
from pipeline.model_records import Catalog, Document, SemanticEmbedding


GENERATED_TIMESTAMP_COLUMNS = {
    ("person", "created_at"),
    ("data_issue", "created_at"),
    ("url_stage", "created_at"),
    ("event_stage", "scraped_datetime"),
    ("event", "scraped_datetime"),
    ("url_stage_hist", "created_at"),
    ("semantic_embedding", "updated_at"),
    ("catalog", "created_at"),
    ("catalog", "uploaded_at"),
    ("document", "created_at"),
}
LIFECYCLE_TIMESTAMP_COLUMNS = {
    ("catalog", "extraction_attempted_at"),
    ("catalog", "lineage_updated_at"),
    ("catalog", "agenda_segmentation_attempted_at"),
}
CANONICAL_TIMESTAMP_COLUMNS = GENERATED_TIMESTAMP_COLUMNS | LIFECYCLE_TIMESTAMP_COLUMNS

MODEL_COLUMNS: dict[tuple[str, str], Column[object]] = {
    ("person", "created_at"): Person.__table__.c.created_at,
    ("data_issue", "created_at"): DataIssue.__table__.c.created_at,
    ("url_stage", "created_at"): UrlStage.__table__.c.created_at,
    ("event_stage", "scraped_datetime"): EventStage.__table__.c.scraped_datetime,
    ("event", "scraped_datetime"): Event.__table__.c.scraped_datetime,
    ("url_stage_hist", "created_at"): UrlStageHist.__table__.c.created_at,
    ("semantic_embedding", "updated_at"): SemanticEmbedding.__table__.c.updated_at,
    ("catalog", "extraction_attempted_at"): Catalog.__table__.c.extraction_attempted_at,
    ("catalog", "lineage_updated_at"): Catalog.__table__.c.lineage_updated_at,
    ("catalog", "agenda_segmentation_attempted_at"): Catalog.__table__.c.agenda_segmentation_attempted_at,
    ("catalog", "created_at"): Catalog.__table__.c.created_at,
    ("catalog", "uploaded_at"): Catalog.__table__.c.uploaded_at,
    ("document", "created_at"): Document.__table__.c.created_at,
}


def _migration_module() -> ModuleType:
    return importlib.import_module("pipeline.migrate_v10")


def _assert_timezone_aware(timestamp_column: Column[object]) -> None:
    assert isinstance(timestamp_column.type, DateTime)
    assert timestamp_column.type.timezone is True


def test_canonical_timestamp_inventory_is_complete_and_typed() -> None:
    migration_module = _migration_module()

    assert is_dataclass(migration_module.TimestampColumnSpec)
    assert migration_module.TimestampColumnSpec.__dataclass_params__.frozen is True
    assert issubclass(migration_module.TimestampMigrationError, RuntimeError)
    assert not hasattr(
        migration_module.TimestampColumnSpec(
            table_name="catalog",
            column_name="created_at",
            has_server_default=True,
        ),
        "__dict__",
    )

    migration_inventory = {
        (timestamp_spec.table_name, timestamp_spec.column_name, timestamp_spec.has_server_default)
        for timestamp_spec in migration_module.TIMESTAMP_COLUMNS
    }
    expected_inventory = {
        (table_name, column_name, (table_name, column_name) in GENERATED_TIMESTAMP_COLUMNS)
        for table_name, column_name in CANONICAL_TIMESTAMP_COLUMNS
    }

    assert migration_inventory == expected_inventory


def test_timestamp_column_spec_is_immutable() -> None:
    migration_module = _migration_module()
    timestamp_spec = migration_module.TimestampColumnSpec(
        table_name="catalog",
        column_name="created_at",
        has_server_default=True,
    )

    with pytest.raises(FrozenInstanceError):
        timestamp_spec.table_name = "document"


@pytest.mark.parametrize("timestamp_identity", sorted(CANONICAL_TIMESTAMP_COLUMNS))
def test_canonical_timestamp_columns_are_timezone_aware(timestamp_identity: tuple[str, str]) -> None:
    _assert_timezone_aware(MODEL_COLUMNS[timestamp_identity])


@pytest.mark.parametrize("timestamp_identity", sorted(GENERATED_TIMESTAMP_COLUMNS))
def test_generated_timestamps_use_server_defaults(timestamp_identity: tuple[str, str]) -> None:
    timestamp_column = MODEL_COLUMNS[timestamp_identity]

    assert timestamp_column.default is None
    assert isinstance(timestamp_column.server_default, DefaultClause)


@pytest.mark.parametrize("timestamp_identity", sorted(LIFECYCLE_TIMESTAMP_COLUMNS))
def test_lifecycle_timestamps_remain_nullable_without_defaults(timestamp_identity: tuple[str, str]) -> None:
    timestamp_column = MODEL_COLUMNS[timestamp_identity]

    assert timestamp_column.nullable is True
    assert timestamp_column.default is None
    assert timestamp_column.server_default is None


def test_semantic_embedding_timestamp_retains_update_behavior() -> None:
    updated_at = SemanticEmbedding.__table__.c.updated_at

    assert updated_at.onupdate is not None


def test_crawler_stage_timestamps_match_canonical_contracts() -> None:
    crawler_url_created_at = crawler_models.UrlStage.__table__.c.created_at
    crawler_event_scraped_at = crawler_models.EventStage.__table__.c.scraped_datetime

    for crawler_timestamp in (crawler_url_created_at, crawler_event_scraped_at):
        _assert_timezone_aware(crawler_timestamp)
        assert crawler_timestamp.default is None
        assert isinstance(crawler_timestamp.server_default, DefaultClause)

    assert crawler_url_created_at.type.timezone == UrlStage.__table__.c.created_at.type.timezone
    assert crawler_event_scraped_at.type.timezone == EventStage.__table__.c.scraped_datetime.type.timezone
