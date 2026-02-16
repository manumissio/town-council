import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pipeline.config import (
    VOTE_EXTRACTION_CONFIDENCE_THRESHOLD,
    VOTE_EXTRACTION_CONTEXT_AFTER_CHARS,
    VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS,
    VOTE_EXTRACTION_MAX_TOKENS,
    VOTE_EXTRACTION_MIN_TEXT_CHARS,
)
from pipeline.models import AgendaItem

logger = logging.getLogger("vote-extractor")

VALID_OUTCOME_LABELS = {
    "passed",
    "failed",
    "deferred",
    "continued",
    "tabled",
    "withdrawn",
    "no_action",
    "unknown",
}

OUTCOME_SYNONYMS = {
    "approved": "passed",
    "adopted": "passed",
    "carried": "passed",
    "accepted": "passed",
    "rejected": "failed",
    "did_not_pass": "failed",
    "did not pass": "failed",
    "denied": "failed",
    "postponed": "continued",
    "held over": "continued",
    "continued to": "continued",
    "referred": "deferred",
    "reconsidered later": "deferred",
    "laid over": "tabled",
    "pulled": "withdrawn",
    "removed": "withdrawn",
    "received and filed": "no_action",
    "discussion only": "no_action",
    "none": "unknown",
    "n/a": "unknown",
}

UNKNOWN_RESULT_VALUES = {"", "unknown", "n/a", "na", "none", "pending", "tbd"}
TRUSTED_VOTE_SOURCES = {"legistar", "manual"}
VOTE_KEYWORDS = (
    "motion",
    "moved",
    "seconded",
    "ayes",
    "noes",
    "abstain",
    "absent",
    "vote",
    "carried",
    "passed",
    "failed",
    "unanimous",
)


@dataclass
class VoteExtractionResult:
    outcome_label: str
    confidence: float
    motion_text: str | None = None
    vote_tally_raw: str | None = None
    yes_count: int | None = None
    no_count: int | None = None
    abstain_count: int | None = None
    absent_count: int | None = None
    evidence_snippet: str | None = None


def prepare_vote_extraction_prompt(item_title: str, item_text: str, meeting_context: str = "") -> str:
    title = " ".join((item_title or "").split())
    context = " ".join((meeting_context or "").split())
    text = (item_text or "").strip()

    return (
        "<start_of_turn>user\n"
        "Extract vote/outcome details for this council agenda item.\n"
        "Return JSON only. No prose. No markdown.\n"
        "Use this exact schema:\n"
        "{\n"
        '  "outcome_label": "passed|failed|deferred|continued|tabled|withdrawn|no_action|unknown",\n'
        '  "motion_text": "string or null",\n'
        '  "vote_tally_raw": "string or null",\n'
        '  "yes_count": "integer or null",\n'
        '  "no_count": "integer or null",\n'
        '  "abstain_count": "integer or null",\n'
        '  "absent_count": "integer or null",\n'
        '  "confidence": "number between 0 and 1",\n'
        '  "evidence_snippet": "short quote-like snippet from source text or null"\n'
        "}\n"
        "Rules:\n"
        "- If no vote/outcome is present, use outcome_label='unknown' and null vote fields.\n"
        "- Do not invent votes.\n"
        "- If explicit voting terms are missing, lower confidence substantially.\n"
        "- Keep evidence_snippet under 220 characters.\n"
        f"Meeting context: {context}\n"
        f"Agenda item title: {title}\n"
        "Item text:\n"
        f"{text}<end_of_turn>\n"
        "<start_of_turn>model\n"
        "{"
    )


def normalize_outcome_label(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    raw = raw.replace("-", "_")
    raw = re.sub(r"\s+", " ", raw)
    if raw in VALID_OUTCOME_LABELS:
        return raw
    if raw in OUTCOME_SYNONYMS:
        return OUTCOME_SYNONYMS[raw]
    if raw.replace(" ", "_") in VALID_OUTCOME_LABELS:
        return raw.replace(" ", "_")
    for synonym, normalized in OUTCOME_SYNONYMS.items():
        if synonym in raw:
            return normalized
    return "unknown"


def _extract_first_json_object(text: str) -> str:
    value = (text or "").strip()
    if not value:
        raise ValueError("empty model output")
    first = value.find("{")
    if first < 0:
        raise ValueError("no json object start")

    depth = 0
    for i in range(first, len(value)):
        char = value[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return value[first : i + 1]
    raise ValueError("unterminated json object")


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not valid integer")
    if isinstance(value, int):
        coerced = value
    else:
        s = str(value).strip()
        if not s:
            return None
        coerced = int(s)
    if coerced < 0:
        raise ValueError("vote counts must be non-negative")
    return coerced


def parse_vote_extraction_response(raw_output: str, council_size: int | None = None) -> VoteExtractionResult:
    payload_text = _extract_first_json_object(raw_output)
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("vote extraction payload is not a JSON object")

    outcome_label = normalize_outcome_label(payload.get("outcome_label"))
    confidence = payload.get("confidence", 0.0)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    confidence_value = max(0.0, min(1.0, confidence_value))

    yes_count = _coerce_optional_int(payload.get("yes_count"))
    no_count = _coerce_optional_int(payload.get("no_count"))
    abstain_count = _coerce_optional_int(payload.get("abstain_count"))
    absent_count = _coerce_optional_int(payload.get("absent_count"))

    if council_size and council_size > 0:
        total = sum(v or 0 for v in (yes_count, no_count, abstain_count, absent_count))
        if total > council_size:
            raise ValueError("vote tally exceeds known council size")

    motion_text = payload.get("motion_text")
    if motion_text is not None:
        motion_text = " ".join(str(motion_text).split())[:500] or None

    vote_tally_raw = payload.get("vote_tally_raw")
    if vote_tally_raw is not None:
        vote_tally_raw = " ".join(str(vote_tally_raw).split())[:300] or None

    evidence_snippet = payload.get("evidence_snippet")
    if evidence_snippet is not None:
        evidence_snippet = " ".join(str(evidence_snippet).split())[:280] or None

    return VoteExtractionResult(
        outcome_label=outcome_label,
        confidence=confidence_value,
        motion_text=motion_text,
        vote_tally_raw=vote_tally_raw,
        yes_count=yes_count,
        no_count=no_count,
        abstain_count=abstain_count,
        absent_count=absent_count,
        evidence_snippet=evidence_snippet,
    )


def extract_vote_outcome(local_ai, item_title: str, item_text: str, meeting_context: str = "") -> VoteExtractionResult:
    prompt = prepare_vote_extraction_prompt(item_title, item_text, meeting_context=meeting_context)
    raw = local_ai.generate_json(prompt, max_tokens=VOTE_EXTRACTION_MAX_TOKENS)
    if not raw:
        raise ValueError("model returned empty vote extraction")
    parsed = parse_vote_extraction_response(raw)
    return _apply_ambiguity_penalty(parsed, item_text)


def _build_vote_context_text(catalog_content: str, item_title: str, item_description: str | None) -> str:
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
            before = max(200, VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS)
            after = max(400, VOTE_EXTRACTION_CONTEXT_AFTER_CHARS)
            start = max(0, match.start() - before)
            end = min(len(content), match.end() + after)
            snippet = content[start:end].strip()
            if snippet:
                sections.append(f"Nearby context: {snippet}")
    return "\n\n".join(sections).strip()


def _result_text_from_label(outcome_label: str) -> str:
    mapping = {
        "passed": "Passed",
        "failed": "Failed",
        "deferred": "Deferred",
        "continued": "Continued",
        "tabled": "Tabled",
        "withdrawn": "Withdrawn",
        "no_action": "No Action",
        "unknown": "Unknown",
    }
    return mapping.get(outcome_label, "Unknown")


def _is_high_confidence_existing_llm_vote(votes: Any) -> bool:
    if not isinstance(votes, dict):
        return False
    source = str(votes.get("source") or "").strip().lower()
    confidence = votes.get("confidence", 0.0)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    return source == "llm_extracted" and confidence_value >= VOTE_EXTRACTION_CONFIDENCE_THRESHOLD


def _is_trusted_existing_vote(votes: Any) -> bool:
    if not isinstance(votes, dict):
        return False
    source = str(votes.get("source") or "").strip().lower()
    return source in TRUSTED_VOTE_SOURCES


def _has_non_unknown_result(result_value: str | None) -> bool:
    return str(result_value or "").strip().lower() not in UNKNOWN_RESULT_VALUES


def _apply_ambiguity_penalty(result: VoteExtractionResult, item_text: str) -> VoteExtractionResult:
    text = (item_text or "").lower()
    has_vote_terms = any(k in text for k in VOTE_KEYWORDS)
    if has_vote_terms:
        return result
    if result.outcome_label in {"unknown", "no_action"}:
        return result
    result.confidence = max(0.0, result.confidence * 0.4)
    return result


def run_vote_extraction_for_catalog(
    db,
    local_ai,
    catalog,
    doc,
    *,
    force: bool = False,
    agenda_items: list[Any] | None = None,
) -> dict:
    items = agenda_items
    if items is None:
        items = db.query(AgendaItem).filter_by(catalog_id=catalog.id).order_by(AgendaItem.order).all()

    counters = {
        "processed_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "skip_reasons": {},
    }
    if not items:
        return counters

    meeting_context = ""
    event = getattr(doc, "event", None)
    if event:
        meeting_context = f"{getattr(event, 'name', '')} {getattr(event, 'record_date', '')}".strip()

    for item in items:
        item_title = str(getattr(item, "title", "") or "").strip()
        if not item_title:
            counters["skipped_items"] += 1
            counters["skip_reasons"]["missing_title"] = counters["skip_reasons"].get("missing_title", 0) + 1
            continue

        # Non-negotiable source hierarchy: Manual > Legistar > LLM.
        if _is_trusted_existing_vote(getattr(item, "votes", None)):
            counters["skipped_items"] += 1
            counters["skip_reasons"]["trusted_source"] = counters["skip_reasons"].get("trusted_source", 0) + 1
            continue

        if not force and _is_high_confidence_existing_llm_vote(getattr(item, "votes", None)):
            counters["skipped_items"] += 1
            counters["skip_reasons"]["already_high_confidence"] = counters["skip_reasons"].get("already_high_confidence", 0) + 1
            continue

        if not force and _has_non_unknown_result(getattr(item, "result", None)):
            counters["skipped_items"] += 1
            counters["skip_reasons"]["existing_result"] = counters["skip_reasons"].get("existing_result", 0) + 1
            continue

        context_text = _build_vote_context_text(
            getattr(catalog, "content", "") or "",
            item_title,
            getattr(item, "description", None),
        )
        if len(context_text) < VOTE_EXTRACTION_MIN_TEXT_CHARS:
            counters["skipped_items"] += 1
            counters["skip_reasons"]["insufficient_text"] = counters["skip_reasons"].get("insufficient_text", 0) + 1
            continue

        counters["processed_items"] += 1
        try:
            extracted = extract_vote_outcome(local_ai, item_title, context_text, meeting_context=meeting_context)
        except Exception as exc:
            counters["failed_items"] += 1
            logger.warning(
                "vote_extraction.failed catalog_id=%s agenda_item_id=%s error=%s",
                catalog.id,
                getattr(item, "id", None),
                exc.__class__.__name__,
            )
            continue

        if extracted.confidence < VOTE_EXTRACTION_CONFIDENCE_THRESHOLD:
            counters["skipped_items"] += 1
            counters["skip_reasons"]["low_confidence"] = counters["skip_reasons"].get("low_confidence", 0) + 1
            continue

        if extracted.outcome_label == "unknown" and all(
            v is None
            for v in (
                extracted.yes_count,
                extracted.no_count,
                extracted.abstain_count,
                extracted.absent_count,
            )
        ):
            counters["skipped_items"] += 1
            counters["skip_reasons"]["unknown_no_tally"] = counters["skip_reasons"].get("unknown_no_tally", 0) + 1
            continue

        item.result = _result_text_from_label(extracted.outcome_label)
        item.votes = {
            "outcome_label": extracted.outcome_label,
            "motion_text": extracted.motion_text,
            "vote_tally_raw": extracted.vote_tally_raw,
            "yes_count": extracted.yes_count,
            "no_count": extracted.no_count,
            "abstain_count": extracted.abstain_count,
            "absent_count": extracted.absent_count,
            "confidence": extracted.confidence,
            "evidence_snippet": extracted.evidence_snippet,
            "source": "llm_extracted",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        counters["updated_items"] += 1
        logger.info(
            "vote_extraction.updated catalog_id=%s agenda_item_id=%s outcome=%s confidence=%.2f",
            catalog.id,
            getattr(item, "id", None),
            extracted.outcome_label,
            extracted.confidence,
        )

    return counters
