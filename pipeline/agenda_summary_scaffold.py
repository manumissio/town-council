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
BUDGET_SIGNAL_WORDS = ("budget", "fund", "appropriation", "contract", "grant", "cost")
POLICY_SIGNAL_WORDS = ("ordinance", "resolution", "zoning", "amendment", "permit", "policy")
PROCESS_SIGNAL_WORDS = ("hearing", "appeal", "review", "consider", "adopt", "approve")


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


def _bluf_seed(total_items: int, money_refs: list[str]) -> str:
    bluf = f"Agenda includes {total_items} substantive item{'s' if total_items != 1 else ''}."
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


def _potential_impacts(combined_text: str, money_refs: list[str]) -> PotentialImpacts:
    potential_impacts = {
        "budget": "Potential fiscal impact is not clearly stated in the agenda text.",
        "policy": "Potential policy or regulatory implications are not fully specified in the agenda text.",
        "process": "The agenda indicates scheduled consideration; final outcomes are not yet available.",
    }
    lowered = combined_text.lower()
    if money_refs or any(word in lowered for word in BUDGET_SIGNAL_WORDS):
        potential_impacts["budget"] = "Budget/funding considerations appear likely based on the agenda language."
    if any(word in lowered for word in POLICY_SIGNAL_WORDS):
        potential_impacts["policy"] = "Policy/regulatory changes may be considered based on listed agenda items."
    if any(word in lowered for word in PROCESS_SIGNAL_WORDS):
        potential_impacts["process"] = "The meeting is positioned for formal review/consideration actions."
    return potential_impacts


def _unknowns(
    items: list[AgendaSummaryItem],
    money_refs: list[str],
    truncation_meta: dict[str, int] | None,
) -> list[str]:
    unknowns = []
    if not money_refs:
        unknowns.append("Specific dollar amounts are not clearly disclosed across the listed items.")
    if not any(normalize_spaces(item.get("result", "")) for item in items):
        unknowns.append("Vote outcomes are not provided in agenda-stage records.")
    if truncation_meta and (truncation_meta.get("items_truncated") or 0) > 0:
        unknowns.append(
            f"Summary generated from first {truncation_meta.get('items_included', 0)} of "
            f"{truncation_meta.get('items_total', 0)} agenda items due to context limits."
        )
    return unknowns or ["Some details remain unspecified in agenda-stage text."]


def _why_this_matters(*, profile: str, single_item_mode: bool, titles: list[str]) -> str:
    if single_item_mode and titles:
        return (
            f"The meeting appears centered on a single high-priority decision: {titles[0]}. "
            "This can concentrate policy attention and public scrutiny on one action item."
        )
    if profile == "risk_first":
        return (
            "The agenda suggests decisions with potential downstream risk and compliance impacts. "
            "Focus on where action language is specific and where details remain undefined."
        )
    return (
        "The agenda indicates upcoming decisions with potential fiscal, policy, or procedural effects. "
        "Residents should focus on listed action items and stated recommendations."
    )


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
        "bluf_seed": _bluf_seed(total_items, money_refs),
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
        "potential_impacts": _potential_impacts(combined_text, money_refs),
        "unknowns": _unknowns(items, money_refs, truncation_meta),
        "single_item_mode": is_single_item_mode,
    }
