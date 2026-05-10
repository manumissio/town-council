from __future__ import annotations

from collections.abc import Sequence
from typing import Any


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

    output_lines = [f"BLUF: Agenda includes {total_items} substantive item{'s' if total_items != 1 else ''}."]
    output_lines.append("Why this matters:")
    output_lines.append(
        "- The agenda indicates upcoming decisions with potential fiscal, policy, or procedural effects."
    )
    output_lines.append("Top actions:")
    if action_lines:
        output_lines.extend(f"- {action}" for action in action_lines)
    else:
        output_lines.append("- No substantive actions were retained after filtering.")
    overflow_count = max(total_items - len(action_lines), 0)
    if overflow_count:
        output_lines.append(f"- (+{overflow_count} more)")
    output_lines.append("Potential impacts:")
    output_lines.append("- Budget: Potential fiscal impact is not clearly stated in the agenda text.")
    output_lines.append(
        "- Policy: Potential policy or regulatory implications are not fully specified in the agenda text."
    )
    output_lines.append(
        "- Process: The agenda indicates scheduled consideration; final outcomes are not yet available."
    )
    output_lines.append("Unknowns:")
    if truncation_meta and (truncation_meta.get("items_truncated") or 0) > 0:
        output_lines.append(
            f"- Summary generated from first {truncation_meta.get('items_included', 0)} of "
            f"{truncation_meta.get('items_total', 0)} agenda items due to context limits."
        )
    else:
        output_lines.append("- Specific dollar amounts are not clearly disclosed across the listed items.")
    output_lines.append("- Vote outcomes are not provided in agenda-stage records.")
    return "\n".join(output_lines).strip()
