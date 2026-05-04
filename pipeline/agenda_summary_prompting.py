from pipeline.agenda_summary_items import AgendaSummaryItem, coerce_agenda_summary_item
from pipeline.agenda_summary_scaffold import AgendaSummaryScaffold, build_agenda_summary_scaffold
from pipeline.agenda_text_heuristics import normalize_spaces


AGENDA_SUMMARY_PROMPT_RULES = (
    "Write a plain-text executive decision brief for a city meeting agenda.\n"
    "STRICT RULES:\n"
    "- Do NOT restate items chronologically.\n"
    "- Do not acknowledge the prompt.\n"
    "- Do NOT invent outcomes or facts not present in input.\n"
    "- Use only provided agenda item fields.\n"
    "- Keep content concrete and concise.\n"
    "REQUIRED FORMAT (exact section headers):\n"
    "BLUF: <one-sentence takeaway>\n"
    "Why this matters:\n"
    "- <1 to 2 bullets>\n"
    "Top actions:\n"
    "- <2 to 6 bullets tied to specific items>\n"
    "Potential impacts:\n"
    "- Budget: <line>\n"
    "- Policy: <line>\n"
    "- Process: <line>\n"
    "Unknowns:\n"
    "- <at least one unknown>\n"
    "If input is truncated, Unknowns must mention partial coverage explicitly.\n"
)
SINGLE_ITEM_PROMPT_RULES = (
    "Single-item mode is active. Include this section as well:\n"
    "Decision/action requested:\n"
    "- <one concrete action line>\n"
)


def _agenda_summary_header(meeting_title: str, meeting_date: str) -> str:
    title = (meeting_title or "").strip()
    date = (meeting_date or "").strip()
    header_parts = [part for part in [title, date] if part]
    return " - ".join(header_parts) if header_parts else "Meeting agenda"


def _agenda_items_prompt_block(items: list[AgendaSummaryItem]) -> str:
    lines = []
    for index, item in enumerate(items):
        title_txt = normalize_spaces(item.get("title", ""))
        desc_txt = normalize_spaces(item.get("description", ""))
        class_txt = normalize_spaces(item.get("classification", ""))
        result_txt = normalize_spaces(item.get("result", ""))
        page = item.get("page_number") or 0
        lines.append(
            f"{index + 1}. Title: {title_txt} | Description: {desc_txt or '(none)'} | "
            f"Classification: {class_txt or '(none)'} | Result: {result_txt or '(none)'} | Page: {page or '(unknown)'}"
        )
    return "\n".join(lines)


def _truncation_note(truncation_meta: dict[str, int] | None) -> str:
    if not truncation_meta or (truncation_meta.get("items_truncated") or 0) <= 0:
        return ""
    return (
        f"Input truncation: included {truncation_meta.get('items_included', 0)} of "
        f"{truncation_meta.get('items_total', 0)} items.\n"
    )


def _scaffold_prompt_block(scaffold: AgendaSummaryScaffold) -> str:
    top_actions_seed = "\n".join(f"- {value}" for value in scaffold.get("top_actions", [])) or "- (none)"
    impacts = scaffold.get("potential_impacts", {})
    unknowns_seed = "\n".join(f"- {value}" for value in scaffold.get("unknowns", [])) or "- (none)"
    return (
        f"Scaffold BLUF seed: {scaffold.get('bluf_seed', '')}\n"
        f"Scaffold Why this matters: {scaffold.get('why_this_matters', '')}\n"
        f"Scaffold Top actions:\n{top_actions_seed}\n"
        "Scaffold Potential impacts:\n"
        f"- Budget: {impacts.get('budget', '')}\n"
        f"- Policy: {impacts.get('policy', '')}\n"
        f"- Process: {impacts.get('process', '')}\n"
        f"Scaffold Unknowns:\n{unknowns_seed}\n\n"
    )


def prepare_structured_agenda_items_summary_prompt(
    meeting_title: str,
    meeting_date: str,
    items: list[AgendaSummaryItem],
    scaffold: AgendaSummaryScaffold,
    truncation_meta: dict[str, int] | None = None,
) -> str:
    instruction = AGENDA_SUMMARY_PROMPT_RULES
    if scaffold.get("single_item_mode"):
        instruction += SINGLE_ITEM_PROMPT_RULES
    return (
        "<start_of_turn>user\n"
        f"{instruction}\n"
        f"Meeting: {_agenda_summary_header(meeting_title, meeting_date)}\n"
        f"{_truncation_note(truncation_meta)}"
        f"{_scaffold_prompt_block(scaffold)}"
        f"Agenda items:\n{_agenda_items_prompt_block(items)}\n"
        "<end_of_turn>\n"
        "<start_of_turn>model\n"
        "BLUF:"
    )


def prepare_agenda_items_summary_prompt(
    meeting_title: str,
    meeting_date: str,
    items: list[str],
    *,
    profile: str,
    max_bullets: int,
    min_item_desc_chars: int,
    single_item_mode: str,
) -> str:
    structured = [coerce_agenda_summary_item(item, idx=index) for index, item in enumerate(items or [])]
    scaffold = build_agenda_summary_scaffold(
        structured,
        truncation_meta=None,
        profile=profile,
        max_bullets=max_bullets,
        min_item_desc_chars=min_item_desc_chars,
        single_item_mode=single_item_mode,
    )
    return prepare_structured_agenda_items_summary_prompt(
        meeting_title=meeting_title,
        meeting_date=meeting_date,
        items=structured,
        scaffold=scaffold,
        truncation_meta=None,
    )
