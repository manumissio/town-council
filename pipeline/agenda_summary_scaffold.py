import re
from typing import TypeAlias

from pipeline.agenda_summary_items import AgendaSummaryItem
from pipeline.agenda_text_heuristics import normalize_spaces


AgendaSummaryScaffold: TypeAlias = dict[str, object]
PotentialImpacts: TypeAlias = dict[str, str]

MONEY_SNIPPET_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d{2})?(?:\s*(?:million|billion|thousand|m|k))?",
    flags=re.IGNORECASE,
)
SOURCE_EXTRACT_NOTICE = "This is an extract of the listed items, not a decision or impact assessment."
IMPACT_NOT_ASSESSED = "Not assessed by this extract. Check the source."
REQUESTED_ACTION_SOURCE_NOTICE = "Check the source text for any requested action."


def extract_money_snippets(text: str) -> list[str]:
    seen = set()
    snippets = []
    for match in MONEY_SNIPPET_RE.findall(text or ""):
        key = match.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        snippets.append(match.strip())
        if len(snippets) >= 5:
            break
    return snippets


def _combined_item_text(items: list[AgendaSummaryItem]) -> str:
    return " ".join(
        f"{item.get('title', '')} {item.get('description', '')} {item.get('result', '')}"
        for item in items
    ).strip()


def build_extracted_item_count_text(total_items: int, money_refs: list[str]) -> str:
    bluf = f"Extracted {total_items} item{'s' if total_items != 1 else ''} from the document."
    if money_refs:
        bluf += f" Mentioned monetary figures include {', '.join(money_refs[:2])}."
    return bluf.strip()


def _top_action_lines(
    items: list[AgendaSummaryItem],
    *,
    max_bullets: int,
    min_item_desc_chars: int,
) -> list[str]:
    top_actions = []
    for item in items[: max(3, min(6, max_bullets))]:
        title = normalize_spaces(item.get("title", ""))
        if not title:
            continue
        desc = normalize_spaces(item.get("description", ""))
        page = item.get("page_number") or 0
        page_hint = f" (p.{page})" if page else ""
        top_actions.append(f"{title}{page_hint}: {desc}" if desc and len(desc) >= min_item_desc_chars else f"{title}{page_hint}")
    return top_actions[:max_bullets]


def _potential_impacts() -> PotentialImpacts:
    # Keywords in a title do not establish consequences or a requested decision.
    return {
        "budget": IMPACT_NOT_ASSESSED,
        "policy": IMPACT_NOT_ASSESSED,
        "process": IMPACT_NOT_ASSESSED,
    }


def build_extracted_item_unknowns(
    items: list[AgendaSummaryItem],
    money_refs: list[str],
    truncation_meta: dict[str, int] | None,
) -> list[str]:
    unknowns = []
    if not money_refs:
        unknowns.append("No monetary amount was supplied in the extracted item fields.")
    if not any(normalize_spaces(item.get("result", "")) for item in items):
        unknowns.append("No result was supplied in the extracted item fields.")
    if truncation_meta and (truncation_meta.get("items_truncated") or 0) > 0:
        unknowns.append(
            f"Summary generated from first {truncation_meta.get('items_included', 0)} of "
            f"{truncation_meta.get('items_total', 0)} agenda items due to context limits."
        )
    return unknowns or ["Read the source for context beyond these item fields."]


def _why_this_matters(*, profile: str, single_item_mode: bool, titles: list[str]) -> str:
    if single_item_mode and titles:
        return f"One item was extracted. {SOURCE_EXTRACT_NOTICE}"
    if profile == "risk_first":
        return f"{SOURCE_EXTRACT_NOTICE} Risks have not been assessed."
    return SOURCE_EXTRACT_NOTICE


def build_agenda_summary_scaffold(
    items: list[AgendaSummaryItem],
    truncation_meta: dict[str, int] | None = None,
    *,
    profile: str,
    max_bullets: int,
    min_item_desc_chars: int,
    single_item_mode: str,
) -> AgendaSummaryScaffold:
    total_items = len(items)
    titles = [str(item.get("title", "")) for item in items if item.get("title")]
    combined_text = _combined_item_text(items)
    money_refs = extract_money_snippets(combined_text)
    is_single_item_mode = bool(total_items == 1 and single_item_mode == "deep_brief")
    return {
        "bluf_seed": build_extracted_item_count_text(total_items, money_refs),
        "why_this_matters": _why_this_matters(
            profile=profile,
            single_item_mode=is_single_item_mode,
            titles=titles,
        ).strip(),
        "top_actions": _top_action_lines(
            items,
            max_bullets=max_bullets,
            min_item_desc_chars=min_item_desc_chars,
        ),
        "potential_impacts": _potential_impacts(),
        "unknowns": build_extracted_item_unknowns(items, money_refs, truncation_meta),
        "single_item_mode": is_single_item_mode,
    }
