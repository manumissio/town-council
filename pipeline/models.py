from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from pipeline.model_base import Base as Base, VECTOR_COLUMN_TYPE as VECTOR_COLUMN_TYPE
from pipeline.model_civic import (
    Membership as Membership,
    Organization as Organization,
    Person as Person,
    Place as Place,
)
from pipeline.model_events import (
    DataIssue as DataIssue,
    Event as Event,
    EventStage as EventStage,
    IssueType as IssueType,
    UrlStage as UrlStage,
    UrlStageHist as UrlStageHist,
)
from pipeline.model_records import (
    AgendaItem as AgendaItem,
    Catalog as Catalog,
    Document as Document,
    SemanticEmbedding as SemanticEmbedding,
)
from pipeline.model_runtime import (
    DATABASE_URL_ENV_VAR as DATABASE_URL_ENV_VAR,
    DATABASE_URL_MISSING_ERROR as DATABASE_URL_MISSING_ERROR,
    POSTGRESQL_MAX_OVERFLOW as POSTGRESQL_MAX_OVERFLOW,
    POSTGRESQL_POOL_RECYCLE_SECONDS as POSTGRESQL_POOL_RECYCLE_SECONDS,
    POSTGRESQL_POOL_SIZE as POSTGRESQL_POOL_SIZE,
    POSTGRESQL_POOL_TIMEOUT as POSTGRESQL_POOL_TIMEOUT,
    POSTGRESQL_SCHEME as POSTGRESQL_SCHEME,
    create_tables as create_tables,
    db_connect_with,
)


def db_connect() -> Engine:
    return db_connect_with(create_engine)
