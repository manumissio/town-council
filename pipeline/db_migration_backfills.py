from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def run_catalog_extraction_backfills(conn: Connection) -> None:
    conn.execute(
        text(
            """
            UPDATE catalog
            SET extraction_status = CASE
                WHEN content IS NOT NULL AND btrim(content) <> '' THEN 'complete'
                ELSE 'pending'
            END
            WHERE extraction_status IS NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE catalog
            SET extraction_attempt_count = COALESCE(extraction_attempt_count, 0)
            WHERE extraction_attempt_count IS NULL
            """
        )
    )


def run_person_type_backfills(conn: Connection) -> None:
    conn.execute(
        text(
            """
            UPDATE person
            SET person_type = 'mentioned'
            WHERE person_type IS NULL OR person_type = ''
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE person
            SET person_type = 'official'
            WHERE is_elected = TRUE
               OR lower(coalesce(current_role, '')) LIKE '%mayor%'
               OR lower(coalesce(current_role, '')) LIKE '%council%'
               OR lower(coalesce(current_role, '')) LIKE '%commissioner%'
               OR id IN (SELECT person_id FROM membership)
            """
        )
    )


def run_core_backfills(conn: Connection) -> None:
    run_catalog_extraction_backfills(conn)
    run_person_type_backfills(conn)
