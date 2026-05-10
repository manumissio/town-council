import re

from pipeline.config import (
    NLP_ENTITY_AGENDA_MAX_TEXT,
    NLP_ENTITY_MIN_CAPITALIZED_NAME_CUES,
    NLP_ENTITY_NONAGENDA_MAX_TEXT,
    NLP_ENTITY_PREFIX_FALLBACK_TEXT,
    NLP_MAX_TEXT_LENGTH,
)

_ENTITY_LINE_HINTS = (
    "roll call",
    "attendance",
    "present:",
    "absent:",
    "ayes",
    "noes",
    "moved by",
    "seconded by",
    "public comment",
    "speaker",
    "speakers",
    "mayor",
    "councilmember",
    "commissioner",
    "chair",
    "vice mayor",
)
_CAPITALIZED_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b")


def empty_entities_payload():
    return {
        "orgs": [],
        "locs": [],
        "persons": [],
    }


def _bounded_join(lines, limit):
    selected = []
    total = 0
    for line in lines:
        compact = " ".join(line.split())
        if not compact:
            continue
        projected = total + len(compact) + (1 if selected else 0)
        if projected > limit and selected:
            break
        if projected > limit:
            compact = compact[:limit]
            projected = len(compact)
        selected.append(compact)
        total = projected
        if total >= limit:
            break
    return "\n".join(selected)


def _looks_low_signal_for_entity_ner(candidate_text):
    if not candidate_text:
        return True

    lowered = candidate_text.lower()
    if any(hint in lowered for hint in _ENTITY_LINE_HINTS):
        return False

    name_cues = _CAPITALIZED_NAME_RE.findall(candidate_text)
    return len(name_cues) < NLP_ENTITY_MIN_CAPITALIZED_NAME_CUES


def build_entity_candidate_text(text, *, category=None):
    if not text:
        return "", {
            "skip_low_signal": True,
            "used_prefix_fallback": False,
            "raw_chars": 0,
            "candidate_chars": 0,
        }

    raw_chars = len(text)
    used_prefix_fallback = False
    normalized_category = (category or "").strip().lower()

    if normalized_category in {"agenda", "agenda_html"}:
        hinted_lines = []
        for line in text.splitlines():
            compact = " ".join(line.split())
            if not compact:
                continue
            lowered = compact.lower()
            if any(hint in lowered for hint in _ENTITY_LINE_HINTS):
                hinted_lines.append(compact)
        candidate_text = _bounded_join(hinted_lines, NLP_ENTITY_AGENDA_MAX_TEXT)
        if not candidate_text:
            candidate_text = text[:NLP_ENTITY_PREFIX_FALLBACK_TEXT]
            used_prefix_fallback = True
    else:
        candidate_text = text[:NLP_ENTITY_NONAGENDA_MAX_TEXT]

    candidate_text = candidate_text[:NLP_MAX_TEXT_LENGTH]
    skip_low_signal = _looks_low_signal_for_entity_ner(candidate_text)
    return candidate_text, {
        "skip_low_signal": skip_low_signal,
        "used_prefix_fallback": used_prefix_fallback,
        "raw_chars": raw_chars,
        "candidate_chars": len(candidate_text),
    }
