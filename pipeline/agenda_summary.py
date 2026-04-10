import logging
import re
from typing import Any

from pipeline.agenda_text_heuristics import (
    is_contact_or_letterhead_noise,
    is_probable_line_fragment_title,
    is_procedural_noise_title,
    looks_like_agenda_segmentation_boilerplate,
    normalize_spaces,
)
from pipeline.config import (
    AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
    AGENDA_SUMMARY_MAX_BULLETS,
    AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
    AGENDA_SUMMARY_PROFILE,
    AGENDA_SUMMARY_SINGLE_ITEM_MODE,
    AGENDA_SUMMARY_TEMPERATURE,
    LLM_SUMMARY_MAX_TOKENS,
)
from pipeline.summary_quality import is_summary_grounded, prune_unsupported_summary_lines
from pipeline.text_generation import (
    normalize_bullets_to_dash,
    strip_llm_acknowledgements,
    strip_markdown_emphasis,
)


logger = logging.getLogger("local-ai")

AGENDA_SUMMARY_COUNTERS_LOG = (
    "agenda_summary.counters total_items=%s kept_items=%s summary_filtered_notice_fragments=%s "
    "agenda_summary_items_total=%s agenda_summary_items_included=%s agenda_summary_items_truncated=%s "
    "agenda_summary_input_chars=%s agenda_summary_single_item_mode=%s agenda_summary_unknowns_count=%s"
)
AGENDA_SUMMARY_FALLBACK_LOG = "agenda_summary.counters agenda_summary_fallback_deterministic=%s"
AGENDA_SUMMARY_GROUNDING_PRUNED_LOG = "agenda_summary.counters agenda_summary_grounding_pruned_lines=%s"


def _serialize_item_for_filtering(item: dict) -> str:
    serialized = item.get("title", "")
    if item.get("description"):
        serialized = f"{serialized} - {item['description']}"
    return serialized


def _split_agenda_summary_item(value: str) -> tuple[str, str]:
    text = normalize_spaces(value)
    if not text:
        return "", ""
    if " - " in text:
        left, right = text.split(" - ", 1)
        return left.strip(), right.strip()
    return text, ""


def _coerce_agenda_summary_item(item, idx: int = 0) -> dict:
    """
    Normalize agenda summary input into a structured record.
    """
    if isinstance(item, dict):
        title = normalize_spaces(item.get("title", ""))
        desc = normalize_spaces(item.get("description", ""))
        classification = normalize_spaces(item.get("classification", ""))
        result = normalize_spaces(item.get("result", ""))
        try:
            page_number = int(item.get("page_number") or 0)
        except (TypeError, ValueError):
            page_number = 0
    else:
        title, desc = _split_agenda_summary_item(normalize_spaces(item or ""))
        classification = ""
        result = ""
        page_number = 0
    return {
        "order": idx + 1,
        "title": title,
        "description": desc,
        "classification": classification,
        "result": result,
        "page_number": page_number,
    }


def _extract_money_snippets(text: str) -> list[str]:
    matches = re.findall(
        r"\$\s?\d[\d,]*(?:\.\d{2})?(?:\s*(?:million|billion|thousand|m|k))?",
        text or "",
        flags=re.IGNORECASE,
    )
    seen = set()
    out = []
    for match in matches:
        key = match.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(match.strip())
        if len(out) >= 5:
            break
    return out


def _agenda_items_source_text(items: list[dict]) -> str:
    lines = []
    for item in items:
        bits = [f"Title: {item.get('title', '')}"]
        if item.get("description"):
            bits.append(f"Description: {item['description']}")
        if item.get("classification"):
            bits.append(f"Classification: {item['classification']}")
        if item.get("result"):
            bits.append(f"Result: {item['result']}")
        if item.get("page_number"):
            bits.append(f"Page: {item['page_number']}")
        lines.append(" | ".join(bits))
    return "\n".join(lines).strip()


def _build_agenda_summary_scaffold(
    items: list[dict],
    truncation_meta: dict | None = None,
    profile: str = "decision_brief",
) -> dict:
    total = len(items)
    titles = [item.get("title", "") for item in items if item.get("title")]
    combined = " ".join(
        f"{item.get('title', '')} {item.get('description', '')} {item.get('result', '')}"
        for item in items
    ).strip()
    money_refs = _extract_money_snippets(combined)

    bluf = f"Agenda includes {total} substantive item{'s' if total != 1 else ''}."
    if money_refs:
        bluf += f" Mentioned monetary figures include {', '.join(money_refs[:2])}."

    top_actions = []
    for item in items[: max(3, min(6, AGENDA_SUMMARY_MAX_BULLETS))]:
        title = normalize_spaces(item.get("title", ""))
        if not title:
            continue
        desc = normalize_spaces(item.get("description", ""))
        page = item.get("page_number") or 0
        page_hint = f" (p.{page})" if page else ""
        if desc and len(desc) >= AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS:
            top_actions.append(f"{title}{page_hint}: {desc}")
        else:
            top_actions.append(f"{title}{page_hint}")

    potential_impacts = {
        "budget": "Potential fiscal impact is not clearly stated in the agenda text.",
        "policy": "Potential policy or regulatory implications are not fully specified in the agenda text.",
        "process": "The agenda indicates scheduled consideration; final outcomes are not yet available.",
    }
    lowered = combined.lower()
    if money_refs or any(word in lowered for word in ("budget", "fund", "appropriation", "contract", "grant", "cost")):
        potential_impacts["budget"] = "Budget/funding considerations appear likely based on the agenda language."
    if any(word in lowered for word in ("ordinance", "resolution", "zoning", "amendment", "permit", "policy")):
        potential_impacts["policy"] = "Policy/regulatory changes may be considered based on listed agenda items."
    if any(word in lowered for word in ("hearing", "appeal", "review", "consider", "adopt", "approve")):
        potential_impacts["process"] = "The meeting is positioned for formal review/consideration actions."

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

    single_item_mode = bool(total == 1 and AGENDA_SUMMARY_SINGLE_ITEM_MODE == "deep_brief")
    if single_item_mode and titles:
        why_this_matters = (
            f"The meeting appears centered on a single high-priority decision: {titles[0]}. "
            "This can concentrate policy attention and public scrutiny on one action item."
        )
    elif profile == "risk_first":
        why_this_matters = (
            "The agenda suggests decisions with potential downstream risk and compliance impacts. "
            "Focus on where action language is specific and where details remain undefined."
        )
    else:
        why_this_matters = (
            "The agenda indicates upcoming decisions with potential fiscal, policy, or procedural effects. "
            "Residents should focus on listed action items and stated recommendations."
        )

    return {
        "bluf_seed": bluf.strip(),
        "why_this_matters": why_this_matters.strip(),
        "top_actions": top_actions[:AGENDA_SUMMARY_MAX_BULLETS],
        "potential_impacts": potential_impacts,
        "unknowns": unknowns or ["Some details remain unspecified in agenda-stage text."],
        "single_item_mode": single_item_mode,
    }


def _prepare_structured_agenda_items_summary_prompt(
    meeting_title: str,
    meeting_date: str,
    items: list[dict],
    scaffold: dict,
    truncation_meta: dict | None = None,
) -> str:
    title = (meeting_title or "").strip()
    date = (meeting_date or "").strip()
    header_parts = [part for part in [title, date] if part]
    header = " - ".join(header_parts) if header_parts else "Meeting agenda"

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
    items_block = "\n".join(lines)

    top_actions_seed = "\n".join(f"- {value}" for value in scaffold.get("top_actions", [])) or "- (none)"
    impacts = scaffold.get("potential_impacts", {})
    unknowns_seed = "\n".join(f"- {value}" for value in scaffold.get("unknowns", [])) or "- (none)"
    truncation_note = ""
    if truncation_meta and (truncation_meta.get("items_truncated") or 0) > 0:
        truncation_note = (
            f"Input truncation: included {truncation_meta.get('items_included', 0)} of "
            f"{truncation_meta.get('items_total', 0)} items.\n"
        )

    instruction = (
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
    if scaffold.get("single_item_mode"):
        instruction += (
            "Single-item mode is active. Include this section as well:\n"
            "Decision/action requested:\n"
            "- <one concrete action line>\n"
        )

    return (
        "<start_of_turn>user\n"
        f"{instruction}\n"
        f"Meeting: {header}\n"
        f"{truncation_note}"
        f"Scaffold BLUF seed: {scaffold.get('bluf_seed', '')}\n"
        f"Scaffold Why this matters: {scaffold.get('why_this_matters', '')}\n"
        f"Scaffold Top actions:\n{top_actions_seed}\n"
        "Scaffold Potential impacts:\n"
        f"- Budget: {impacts.get('budget', '')}\n"
        f"- Policy: {impacts.get('policy', '')}\n"
        f"- Process: {impacts.get('process', '')}\n"
        f"Scaffold Unknowns:\n{unknowns_seed}\n\n"
        f"Agenda items:\n{items_block}\n"
        "<end_of_turn>\n"
        "<start_of_turn>model\n"
        "BLUF:"
    )


def prepare_agenda_items_summary_prompt(meeting_title: str, meeting_date: str, items: list[str]) -> str:
    """
    Backwards-compatible wrapper for legacy tests/callers.
    """
    structured = [_coerce_agenda_summary_item(item, idx=index) for index, item in enumerate(items or [])]
    scaffold = _build_agenda_summary_scaffold(structured, truncation_meta=None, profile=AGENDA_SUMMARY_PROFILE)
    return _prepare_structured_agenda_items_summary_prompt(
        meeting_title=meeting_title,
        meeting_date=meeting_date,
        items=structured,
        scaffold=scaffold,
        truncation_meta=None,
    )


def _agenda_items_summary_is_too_short(text: str) -> bool:
    if not text:
        return True
    value = text.strip()
    if len(value) < 220:
        return True
    lower = value.lower()
    required_sections = ("why this matters:", "top actions:", "potential impacts:", "unknowns:")
    if any(section not in lower for section in required_sections):
        return True
    bullet_lines = [line for line in value.splitlines() if line.strip().startswith("- ")]
    if len(bullet_lines) < 5:
        return True

    top_actions = 0
    in_top_actions = False
    for line in value.splitlines():
        stripped = line.strip().lower()
        if stripped == "top actions:":
            in_top_actions = True
            continue
        if stripped.endswith(":") and stripped != "top actions:":
            in_top_actions = False
        if in_top_actions and line.strip().startswith("- "):
            top_actions += 1
    return top_actions < 2


def _ensure_single_item_decision_section(text: str, scaffold: dict) -> str:
    value = (text or "").strip()
    if not value or not scaffold.get("single_item_mode"):
        return value
    if re.search(r"(?im)^decision/action requested:\s*$", value):
        return value

    actions = scaffold.get("top_actions", [])
    default_line = actions[0] if actions else "The agenda focuses on one primary action item."
    block = f"Decision/action requested:\n- {default_line}\n"
    if re.search(r"(?im)^top actions:\s*$", value):
        return re.sub(r"(?im)^top actions:\s*$", block + "Top actions:", value, count=1)
    return value + "\n" + block


def deterministic_agenda_items_summary(
    items,
    max_bullets: int = 25,
    truncation_meta: dict | None = None,
) -> str:
    """
    Deterministic fallback summary for agendas.
    """
    structured = [_coerce_agenda_summary_item(item, idx=index) for index, item in enumerate(items or [])]
    scaffold = _build_agenda_summary_scaffold(structured, truncation_meta=truncation_meta)
    shown = scaffold.get("top_actions", [])[:max_bullets]

    output_lines = [f"BLUF: {scaffold.get('bluf_seed', 'Agenda summary unavailable.')}"]
    output_lines.append("Why this matters:")
    output_lines.append(
        f"- {scaffold.get('why_this_matters', 'This agenda includes planned council actions.')}"
    )
    output_lines.append("Top actions:")
    if shown:
        output_lines.extend(f"- {item}" for item in shown)
    else:
        output_lines.append("- No substantive actions were retained after filtering.")
    if scaffold.get("single_item_mode"):
        output_lines.append("Decision/action requested:")
        output_lines.append(
            f"- {(shown[0] if shown else 'The agenda focuses on one primary action item.')}"
        )

    impacts = scaffold.get("potential_impacts", {})
    output_lines.append("Potential impacts:")
    output_lines.append(f"- Budget: {impacts.get('budget', 'Not clearly stated.')}")
    output_lines.append(f"- Policy: {impacts.get('policy', 'Not clearly stated.')}")
    output_lines.append(f"- Process: {impacts.get('process', 'Not clearly stated.')}")
    output_lines.append("Unknowns:")
    for unknown in scaffold.get("unknowns", []):
        output_lines.append(f"- {unknown}")
    return "\n".join(output_lines).strip()


def _should_drop_from_agenda_summary(item_text: str) -> bool:
    title, desc = _split_agenda_summary_item(item_text)
    if not title:
        return True
    title_looks_noisy = (
        looks_like_agenda_segmentation_boilerplate(title)
        or is_procedural_noise_title(title)
        or is_contact_or_letterhead_noise(title, desc)
        or is_probable_line_fragment_title(title)
    )
    if not title_looks_noisy:
        return False
    return len(normalize_spaces(desc)) < AGENDA_MIN_SUBSTANTIVE_DESC_CHARS


def _normalize_model_agenda_summary_output(text: str, scaffold: dict) -> str:
    cleaned = strip_markdown_emphasis(text).strip()
    cleaned = strip_llm_acknowledgements(cleaned).strip()
    cleaned = normalize_bullets_to_dash(cleaned).strip()
    if cleaned and not cleaned.startswith("BLUF:"):
        cleaned = f"BLUF: {scaffold.get('bluf_seed', 'Agenda summary.')}"
    return _ensure_single_item_decision_section(cleaned, scaffold)


def _build_summary_counters(
    structured_items: list[dict],
    filtered_items: list[dict],
    scaffold: dict,
    truncation_meta: dict | None,
) -> dict[str, int]:
    return {
        "agenda_summary_items_total": len(structured_items),
        "agenda_summary_items_included": len(filtered_items),
        "agenda_summary_items_truncated": int((truncation_meta or {}).get("items_truncated", 0)),
        "agenda_summary_input_chars": int((truncation_meta or {}).get("input_chars", 0)),
        "agenda_summary_single_item_mode": int(bool(scaffold.get("single_item_mode"))),
        "agenda_summary_unknowns_count": len(scaffold.get("unknowns", [])),
        "agenda_summary_grounding_pruned_lines": 0,
        "agenda_summary_fallback_deterministic": 0,
    }


def _log_summary_counters(
    *,
    total_items: int,
    filtered_items: int,
    filtered_notice_fragments: int,
    counters: dict[str, int],
) -> None:
    logger.info(
        AGENDA_SUMMARY_COUNTERS_LOG,
        total_items,
        filtered_items,
        filtered_notice_fragments,
        counters["agenda_summary_items_total"],
        counters["agenda_summary_items_included"],
        counters["agenda_summary_items_truncated"],
        counters["agenda_summary_input_chars"],
        counters["agenda_summary_single_item_mode"],
        counters["agenda_summary_unknowns_count"],
    )


def _log_deterministic_fallback(counters: dict[str, int]) -> None:
    counters["agenda_summary_fallback_deterministic"] = 1
    logger.info(AGENDA_SUMMARY_FALLBACK_LOG, 1)


def run_agenda_summary_pipeline(
    provider: Any,
    *,
    meeting_title: str,
    meeting_date: str,
    items: list[Any] | None,
    truncation_meta: dict | None,
) -> str:
    structured_items = [_coerce_agenda_summary_item(item, index) for index, item in enumerate(items or [])]
    filtered_items = []
    filtered_notice_fragments = 0
    for item in structured_items:
        if _should_drop_from_agenda_summary(_serialize_item_for_filtering(item)):
            filtered_notice_fragments += 1
            continue
        filtered_items.append(item)

    scaffold = _build_agenda_summary_scaffold(filtered_items, truncation_meta)
    counters = _build_summary_counters(structured_items, filtered_items, scaffold, truncation_meta)
    _log_summary_counters(
        total_items=len(structured_items),
        filtered_items=len(filtered_items),
        filtered_notice_fragments=filtered_notice_fragments,
        counters=counters,
    )

    if not filtered_items:
        _log_deterministic_fallback(counters)
        return deterministic_agenda_items_summary([], AGENDA_SUMMARY_MAX_BULLETS, truncation_meta)

    prompt = _prepare_structured_agenda_items_summary_prompt(
        meeting_title,
        meeting_date,
        filtered_items,
        scaffold,
        truncation_meta,
    )
    grounding_source = _agenda_items_source_text(filtered_items)
    raw_summary = (
        provider.summarize_agenda_items(
            prompt,
            max_tokens=LLM_SUMMARY_MAX_TOKENS,
            temperature=AGENDA_SUMMARY_TEMPERATURE,
        )
        or ""
    ).strip()
    cleaned_summary = _normalize_model_agenda_summary_output(raw_summary, scaffold)

    pruned_summary, removed_count = prune_unsupported_summary_lines(cleaned_summary, grounding_source)
    counters["agenda_summary_grounding_pruned_lines"] = int(removed_count)
    if removed_count:
        logger.info(AGENDA_SUMMARY_GROUNDING_PRUNED_LOG, removed_count)
    cleaned_summary = pruned_summary or cleaned_summary

    grounded_summary = is_summary_grounded(cleaned_summary, grounding_source)
    if (not grounded_summary.is_grounded) or _agenda_items_summary_is_too_short(cleaned_summary):
        _log_deterministic_fallback(counters)
        return deterministic_agenda_items_summary(
            filtered_items,
            AGENDA_SUMMARY_MAX_BULLETS,
            truncation_meta,
        )
    return cleaned_summary
