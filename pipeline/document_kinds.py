from __future__ import annotations

from typing import Any

from sqlalchemy import case, func


def normalize_summary_doc_kind(raw_kind: str | None) -> str:
    """
    Normalize crawler document categories into summary-routing kinds.

    Why this exists:
    Crawlers may keep source-specific detail such as "agenda_html", while summary
    routing needs stable agenda/minutes semantics across cities.
    """
    kind = (raw_kind or "").strip().lower()
    if kind in {"agenda", "agenda_html"}:
        return "agenda"
    if kind == "minutes":
        return "minutes"
    return "unknown"


def summary_doc_kind_sql_expr(column: Any) -> Any:
    lowered = func.lower(func.coalesce(column, ""))
    return case(
        (lowered.in_(("agenda", "agenda_html")), "agenda"),
        (lowered == "minutes", "minutes"),
        else_="unknown",
    )
