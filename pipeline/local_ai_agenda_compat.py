from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pipeline.agenda_summary_items import agenda_items_source_text, coerce_agenda_summary_item
from pipeline.agenda_summary_scaffold import (
    IMPACT_NOT_ASSESSED,
    SOURCE_EXTRACT_NOTICE,
    build_extracted_item_count_text,
    build_extracted_item_unknowns,
    extract_money_snippets,
)


def agenda_items_summary_is_too_short(text: str) -> bool:
    """
    Preserve the legacy helper contract for direct callers/tests.
    """
    if not text:
        return True
    value = text.strip()
    if len(value) < 80:
        return True
    if value.lower().startswith("bluf: hi."):
        return True
    bullet_lines = [line for line in value.splitlines() if line.strip().startswith("- ")]
    return len(bullet_lines) < 3


def deterministic_agenda_items_summary(
    items: Sequence[Any] | None,
    max_bullets: int = 25,
    truncation_meta: dict[str, Any] | None = None,
) -> str:
    """
    Preserve the older compatibility shape exposed from `pipeline.llm`.
    """
    total_items = len(items or [])
    action_lines: list[str] = []
    for item in (items or [])[:max_bullets]:
        if isinstance(item, dict):
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            page_number = int(item.get("page_number") or 0)
        else:
            title = str(item or "").strip()
            description = ""
            page_number = 0
        if not title:
            continue
        page_suffix = f" (p.{page_number})" if page_number else ""
        action_lines.append(f"{title}{page_suffix}" if not description else f"{title}{page_suffix}: {description}")

    structured_items = [coerce_agenda_summary_item(item, idx=index) for index, item in enumerate(items or [])]
    money_refs = extract_money_snippets(agenda_items_source_text(structured_items))
    output_lines = [f"BLUF: {build_extracted_item_count_text(total_items, money_refs)}"]
    output_lines.append("Why this matters:")
    output_lines.append(f"- {SOURCE_EXTRACT_NOTICE}")
    output_lines.append("Top actions:")
    if action_lines:
        output_lines.extend(f"- {action}" for action in action_lines)
    else:
        output_lines.append("- No items were retained after filtering.")
    overflow_count = max(total_items - len(action_lines), 0)
    if overflow_count:
        output_lines.append(f"- (+{overflow_count} more)")
    output_lines.append("Potential impacts:")
    output_lines.append(f"- Budget: {IMPACT_NOT_ASSESSED}")
    output_lines.append(f"- Policy: {IMPACT_NOT_ASSESSED}")
    output_lines.append(f"- Process: {IMPACT_NOT_ASSESSED}")
    output_lines.append("Unknowns:")
    output_lines.extend(
        f"- {unknown}" for unknown in build_extracted_item_unknowns(structured_items, money_refs, truncation_meta)
    )
    return "\n".join(output_lines).strip()
