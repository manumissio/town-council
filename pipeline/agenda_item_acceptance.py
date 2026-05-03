from __future__ import annotations

import re

from pipeline.agenda_text_noise import (
    is_contact_or_letterhead_noise,
    is_procedural_noise_title,
    looks_like_sub_marker_title,
)
from pipeline.agenda_text_normalization import normalize_spaces
from pipeline.config import AGENDA_MIN_SUBSTANTIVE_DESC_CHARS, AGENDA_MIN_TITLE_CHARS


_LLM_RECALL_THRESHOLD = 0.28
_LLM_BALANCED_THRESHOLD = 0.45
_LLM_AGGRESSIVE_THRESHOLD = 0.58
_MAX_TABULAR_FRAGMENT_CHARS = 180
_STRONG_TABULAR_MAX_CHARS = 150
_SECONDARY_TABULAR_MAX_CHARS = 120
_LOW_ALPHA_DENSITY_THRESHOLD = 0.60
_PRIMARY_NUMBER_SYMBOL_RATIO = 0.25
_SECONDARY_NUMBER_SYMBOL_RATIO = 0.35
_TABULAR_VERB_LIKE_TOKENS = (
    "approve",
    "adopt",
    "authorize",
    "consider",
    "review",
    "receive",
    "conduct",
    "hold",
    "amend",
    "create",
    "repeal",
    "establish",
    "select",
)


def llm_item_substance_score(title: object, desc: object = "") -> float:
    """
    Score how likely this looks like a substantive legislative item (0.0-1.0).
    """
    title_norm = normalize_spaces(title)
    desc_norm = normalize_spaces(desc)
    lowered = f"{title_norm} {desc_norm}".lower()
    score = 0.20

    if len(title_norm) >= AGENDA_MIN_TITLE_CHARS:
        score += 0.15

    if is_procedural_noise_title(title_norm):
        score -= 0.45
    if is_contact_or_letterhead_noise(title_norm, desc_norm):
        score -= 0.45

    if any(term in lowered for term in _legislative_terms()):
        score += 0.35
    if any(term in lowered for term in ("approve", "adopt", "authorize", "consider", "review", "receive", "vote")):
        score += 0.15
    if len(desc_norm) >= AGENDA_MIN_SUBSTANTIVE_DESC_CHARS:
        score += 0.20

    return max(0.0, min(1.0, score))


def is_tabular_fragment(title: str, desc: str = "", context: dict[str, object] | None = None) -> bool:
    """
    Detect flattened table/list rows that should not be promoted to top-level agenda items.
    """
    raw_title = title or ""
    raw_desc = desc or ""
    raw_combined = f"{raw_title} {raw_desc}".strip()
    combined = normalize_spaces(raw_combined)
    if not combined or len(combined) > _MAX_TABULAR_FRAGMENT_CHARS:
        return False

    tokens = [token for token in re.split(r"\s+", combined.lower()) if token]
    number_symbol_ratio = _number_symbol_ratio(tokens)
    strong_primary = _has_strong_tabular_signal(combined, number_symbol_ratio)

    secondary_signals = _tabular_secondary_signal_count(raw_title, raw_combined, tokens, context)
    has_active_parent = bool((context or {}).get("has_active_parent"))
    if strong_primary:
        return True
    if has_active_parent and secondary_signals >= 2:
        return True
    return secondary_signals >= 3 and len(combined) <= _SECONDARY_TABULAR_MAX_CHARS


def should_accept_llm_item(item: dict[str, object], mode: str = "balanced") -> bool:
    """
    Acceptance gate for LLM-parsed items only.
    """
    title = normalize_spaces(item.get("title", ""))
    desc = normalize_spaces(item.get("description", ""))
    context = item.get("context") if isinstance(item, dict) else None
    context_payload = context if isinstance(context, dict) else None
    if len(title) < AGENDA_MIN_TITLE_CHARS:
        return False
    if is_procedural_noise_title(title):
        return False
    if is_contact_or_letterhead_noise(title, desc):
        return False
    if is_tabular_fragment(title, desc, context=context_payload):
        return False

    threshold = _acceptance_threshold(mode)
    score = llm_item_substance_score(title, desc)

    if len(desc) < AGENDA_MIN_SUBSTANTIVE_DESC_CHARS and score < threshold:
        return False
    return score >= threshold


def _legislative_terms() -> tuple[str, ...]:
    return (
        "ordinance",
        "resolution",
        "contract",
        "budget",
        "zoning",
        "amendment",
        "plan",
        "program",
        "agreement",
        "hearing",
        "permit",
        "funding",
        "project",
        "recommendation",
        "policy",
        "appeal",
        "allocation",
    )


def _number_symbol_ratio(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    number_symbol_tokens = sum(1 for token in tokens if re.search(r"[0-9$%/|#]", token))
    return number_symbol_tokens / len(tokens)


def _has_strong_tabular_signal(combined: str, number_symbol_ratio: float) -> bool:
    total_chars = len(combined)
    alpha_chars = sum(1 for char in combined if char.isalpha())
    alpha_density = (alpha_chars / total_chars) if total_chars else 1.0
    return (
        len(combined) <= _STRONG_TABULAR_MAX_CHARS
        and alpha_density < _LOW_ALPHA_DENSITY_THRESHOLD
        and number_symbol_ratio >= _PRIMARY_NUMBER_SYMBOL_RATIO
    )


def _tabular_secondary_signal_count(
    raw_title: str,
    raw_combined: str,
    tokens: list[str],
    context: dict[str, object] | None,
) -> int:
    secondary_signals = 0
    if "\t" in raw_combined or re.search(r" {3,}", raw_combined):
        secondary_signals += 1
    if bool((context or {}).get("has_active_parent")) and looks_like_sub_marker_title(raw_title):
        secondary_signals += 1
    if tokens and _number_symbol_ratio(tokens) >= _SECONDARY_NUMBER_SYMBOL_RATIO:
        secondary_signals += 1
    if len(tokens) >= 5 and not any(verb in " ".join(tokens) for verb in _TABULAR_VERB_LIKE_TOKENS):
        secondary_signals += 1
    return secondary_signals


def _acceptance_threshold(mode: str) -> float:
    threshold_map = {
        "recall": _LLM_RECALL_THRESHOLD,
        "balanced": _LLM_BALANCED_THRESHOLD,
        "aggressive": _LLM_AGGRESSIVE_THRESHOLD,
    }
    return threshold_map.get((mode or "balanced").lower(), threshold_map["balanced"])
