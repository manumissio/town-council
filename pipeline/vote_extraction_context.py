from __future__ import annotations

import re


def build_vote_context_text(
    catalog_content: str,
    item_title: str,
    item_description: str | None,
    *,
    context_before_chars: int,
    context_after_chars: int,
) -> str:
    sections: list[str] = []
    if item_title:
        sections.append(f"Title: {item_title}")
    if item_description:
        sections.append(f"Description: {item_description}")

    content = catalog_content or ""
    title = (item_title or "").strip()
    if content and title:
        match = re.search(re.escape(title), content, flags=re.IGNORECASE)
        if match:
            before = max(200, context_before_chars)
            after = max(400, context_after_chars)
            start = max(0, match.start() - before)
            end = min(len(content), match.end() + after)
            snippet = content[start:end].strip()
            if snippet:
                sections.append(f"Nearby context: {snippet}")
    return "\n\n".join(sections).strip()


def build_meeting_context(event: object | None) -> str:
    if not event:
        return ""
    return f"{getattr(event, 'name', '')} {getattr(event, 'record_date', '')}".strip()
