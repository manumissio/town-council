"""Startup purge for derived catalog data in dev environments.

This keeps source ingest records intact while clearing generated content that can
be stale or misleading after container restarts.
"""

from __future__ import annotations

import logging
import os
from typing import Dict

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from pipeline.models import AgendaItem, Catalog, db_connect

logger = logging.getLogger("startup-purge")

# Fixed lock key used with PostgreSQL advisory locks.
# We lock so only one service purges during a startup wave.
PURGE_LOCK_KEY = 891004221


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def purge_derived_state(session) -> Dict[str, int]:
    """Clear derived rows/fields while preserving source ingest records."""
    deleted_agenda_items = session.query(AgendaItem).delete(synchronize_session=False)

    cleared_catalog_rows = session.query(Catalog).update(
        {
            Catalog.content: None,
            Catalog.summary: None,
            Catalog.summary_extractive: None,
            Catalog.topics: None,
            Catalog.entities: None,
            Catalog.related_ids: None,
            Catalog.tables: None,
            Catalog.content_hash: None,
            Catalog.summary_source_hash: None,
            Catalog.topics_source_hash: None,
        },
        synchronize_session=False,
    )

    return {
        "deleted_agenda_items": int(deleted_agenda_items or 0),
        "cleared_catalog_rows": int(cleared_catalog_rows or 0),
    }


def _should_run_purge() -> tuple[bool, str]:
    if not _env_bool("STARTUP_PURGE_DERIVED", False):
        return False, "disabled"

    app_env = (os.getenv("APP_ENV") or "dev").strip().lower()
    if app_env == "dev":
        return True, "enabled"

    if _env_bool("STARTUP_PURGE_ALLOW_NON_DEV", False):
        return True, "enabled_non_dev_override"

    required = os.getenv("STARTUP_PURGE_REQUIRED_TOKEN", "")
    provided = os.getenv("STARTUP_PURGE_CONFIRM_TOKEN", "")
    if required and provided and required == provided:
        return True, "enabled_non_dev_token"

    return False, "blocked_non_dev"


def run_startup_purge_if_enabled() -> Dict[str, object]:
    """Run startup purge once per startup wave when enabled by environment."""
    should_run, reason = _should_run_purge()
    if not should_run:
        result = {"status": "skipped", "reason": reason}
        logger.info("startup_purge.skipped", extra=result)
        return result

    engine = db_connect()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    lock_acquired = True
    try:
        logger.info("startup_purge.started")

        if engine.dialect.name == "postgresql":
            lock_acquired = bool(
                session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": PURGE_LOCK_KEY},
                ).scalar()
            )
            if not lock_acquired:
                session.rollback()
                result = {"status": "skipped", "reason": "lock_not_acquired"}
                logger.info("startup_purge.skipped", extra=result)
                return result

        counts = purge_derived_state(session)
        session.commit()
        result = {"status": "completed", **counts}
        logger.info("startup_purge.completed", extra=result)
        return result

    except Exception as exc:
        session.rollback()
        logger.exception("startup_purge.failed")
        return {"status": "failed", "error": str(exc)}

    finally:
        if engine.dialect.name == "postgresql" and lock_acquired:
            try:
                session.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": PURGE_LOCK_KEY},
                )
                session.commit()
            except Exception:
                session.rollback()
        session.close()
