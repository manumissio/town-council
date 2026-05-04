import re

from pipeline.agenda_summary_items import coerce_agenda_summary_item
from pipeline.agenda_summary_scaffold import AgendaSummaryScaffold, build_agenda_summary_scaffold
from pipeline.text_generation import (
    normalize_bullets_to_dash,
    strip_llm_acknowledgements,
    strip_markdown_emphasis,
)


REQUIRED_RUNTIME_SUMMARY_SECTIONS = ("why this matters:", "top actions:", "potential impacts:", "unknowns:")
MIN_RUNTIME_SUMMARY_CHARS = 220
MIN_RUNTIME_SUMMARY_BULLETS = 5
MIN_TOP_ACTION_BULLETS = 2
TOP_ACTIONS_HEADER = "top actions:"
DECISION_ACTION_HEADER_RE = re.compile(r"(?im)^decision/action requested:\s*$")
TOP_ACTIONS_HEADER_RE = re.compile(r"(?im)^top actions:\s*$")


def agenda_items_summary_is_too_short(text: str) -> bool:
    if not text:
        return True
    value = text.strip()
    if len(value) < MIN_RUNTIME_SUMMARY_CHARS:
        return True
    lower = value.lower()
    if any(section not in lower for section in REQUIRED_RUNTIME_SUMMARY_SECTIONS):
        return True
    bullet_lines = [line for line in value.splitlines() if line.strip().startswith("- ")]
    if len(bullet_lines) < MIN_RUNTIME_SUMMARY_BULLETS:
        return True
    return _top_action_count(value) < MIN_TOP_ACTION_BULLETS


def _top_action_count(text: str) -> int:
    top_actions = 0
    in_top_actions = False
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped == TOP_ACTIONS_HEADER:
            in_top_actions = True
            continue
        if stripped.endswith(":") and stripped != TOP_ACTIONS_HEADER:
            in_top_actions = False
        if in_top_actions and line.strip().startswith("- "):
            top_actions += 1
    return top_actions


def ensure_single_item_decision_section(text: str, scaffold: AgendaSummaryScaffold) -> str:
    value = (text or "").strip()
    if not value or not scaffold.get("single_item_mode"):
        return value
    if DECISION_ACTION_HEADER_RE.search(value):
        return value

    actions = scaffold.get("top_actions", [])
    default_line = actions[0] if actions else "The agenda focuses on one primary action item."
    block = f"Decision/action requested:\n- {default_line}\n"
    if TOP_ACTIONS_HEADER_RE.search(value):
        return TOP_ACTIONS_HEADER_RE.sub(block + "Top actions:", value, count=1)
    return value + "\n" + block


def deterministic_agenda_items_summary(
    items: list[object] | None,
    max_bullets: int,
    truncation_meta: dict[str, int] | None,
    *,
    profile: str,
    min_item_desc_chars: int,
    single_item_mode: str,
) -> str:
    structured = [coerce_agenda_summary_item(item, idx=index) for index, item in enumerate(items or [])]
    scaffold = build_agenda_summary_scaffold(
        structured,
        truncation_meta=truncation_meta,
        profile=profile,
        max_bullets=max_bullets,
        min_item_desc_chars=min_item_desc_chars,
        single_item_mode=single_item_mode,
    )
    return _render_scaffold_summary(scaffold, max_bullets)


def _render_scaffold_summary(scaffold: AgendaSummaryScaffold, max_bullets: int) -> str:
    shown = list(scaffold.get("top_actions", []))[:max_bullets]
    output_lines = [
        f"BLUF: {scaffold.get('bluf_seed', 'Agenda summary unavailable.')}",
        "Why this matters:",
        f"- {scaffold.get('why_this_matters', 'This agenda includes planned council actions.')}",
        "Top actions:",
    ]
    output_lines.extend(f"- {item}" for item in shown) if shown else output_lines.append(
        "- No substantive actions were retained after filtering."
    )
    if scaffold.get("single_item_mode"):
        output_lines.extend(["Decision/action requested:", f"- {(shown[0] if shown else 'The agenda focuses on one primary action item.')}"])

    impacts = scaffold.get("potential_impacts", {})
    output_lines.extend(
        [
            "Potential impacts:",
            f"- Budget: {impacts.get('budget', 'Not clearly stated.')}",
            f"- Policy: {impacts.get('policy', 'Not clearly stated.')}",
            f"- Process: {impacts.get('process', 'Not clearly stated.')}",
            "Unknowns:",
        ]
    )
    output_lines.extend(f"- {unknown}" for unknown in scaffold.get("unknowns", []))
    return "\n".join(output_lines).strip()


def normalize_model_agenda_summary_output(text: str, scaffold: AgendaSummaryScaffold) -> str:
    cleaned = strip_markdown_emphasis(text).strip()
    cleaned = strip_llm_acknowledgements(cleaned).strip()
    cleaned = normalize_bullets_to_dash(cleaned).strip()
    if cleaned and not cleaned.startswith("BLUF:"):
        cleaned = f"BLUF: {scaffold.get('bluf_seed', 'Agenda summary.')}"
    return ensure_single_item_decision_section(cleaned, scaffold)
