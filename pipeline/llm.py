import os
import logging
import threading
import re
from rapidfuzz import fuzz

try:
    # Optional dependency: we still want the pipeline to run (heuristic fallbacks)
    # even if llama-cpp isn't installed in the current environment.
    from llama_cpp import Llama
except Exception:  # pragma: no cover
    Llama = None

from pipeline.agenda_extraction import (
    AgendaExtractionHelpers,
    build_agenda_extraction_prompt,
    iter_fallback_paragraphs as iter_fallback_paragraphs_impl,
    parse_llm_agenda_items as parse_llm_agenda_items_impl,
    run_agenda_extraction_pipeline,
)
from pipeline.agenda_summary import AgendaSummaryHelpers, run_agenda_summary_pipeline
from pipeline.config import (
    LLM_CONTEXT_WINDOW,
    LLM_SUMMARY_MAX_TEXT,
    LLM_SUMMARY_MAX_TOKENS,
    LLM_AGENDA_MAX_TEXT,
    LLM_AGENDA_MAX_TOKENS,
    AGENDA_SEGMENTATION_MODE,
    AGENDA_MIN_TITLE_CHARS,
    AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
    AGENDA_TOC_DEDUP_FUZZ,
    AGENDA_PROCEDURAL_REJECT_ENABLED,
    AGENDA_SUMMARY_PROFILE,
    AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
    AGENDA_SUMMARY_MAX_BULLETS,
    AGENDA_SUMMARY_SINGLE_ITEM_MODE,
    LOCAL_AI_ALLOW_MULTIPROCESS,
    LOCAL_AI_BACKEND,
    LOCAL_AI_REQUIRE_SOLO_POOL,
)
from pipeline.runtime_guardrails import (
    local_ai_guardrail_inputs_from_env,
    local_ai_runtime_guardrail_message,
)
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.lexicon import (
    is_procedural_title as lexicon_is_procedural_title,
    is_contact_or_letterhead_noise as lexicon_is_contact_or_letterhead_noise,
    normalize_title_key as lexicon_normalize_title_key,
)
from pipeline.llm_provider import (
    InProcessLlamaProvider,
    HttpInferenceProvider,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderResponseError,
)

# Setup logging
logger = logging.getLogger("local-ai")

_SUMMARY_DOC_KINDS = {"minutes", "agenda", "unknown"}

class LocalAIConfigError(RuntimeError):
    """
    Raised when LocalAI is invoked in an unsafe/unsupported runtime configuration.
    """

def _dedupe_lines_preserve_order(lines):
    """Return unique lines while keeping the first occurrence order."""
    out = []
    seen = set()
    for line in lines:
        key = line.strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _normalize_spaces(value: str) -> str:
    if value is None:
        raw = ""
    elif isinstance(value, str):
        raw = value
    else:
        # Some tests use MagicMock placeholders for optional fields.
        raw = str(value)
    return re.sub(r"\s+", " ", raw).strip()


def _normalized_title_key(value: str) -> str:
    # Single lexicon source keeps normalization consistent across pipeline/API.
    return lexicon_normalize_title_key(_normalize_spaces(value))

def _first_alpha_char(value: str) -> str | None:
    """
    Return the first alphabetical character in a string, or None when absent.
    """
    match = re.search(r"[a-zA-Z]", value or "")
    return match.group(0) if match else None


def _is_probable_line_fragment_title(title: str) -> bool:
    """
    Detect line-fragment titles from pleading-paper numbering/OCR artifacts.

    Why this is fallback-scoped:
    Heuristic fallback parsing sees raw lines like "16 in the appropriate ...".
    We only apply this trap there, not to direct LLM-parsed items.
    """
    normalized = _normalize_spaces(title)
    if not normalized:
        return True

    first_alpha = _first_alpha_char(normalized)
    if not first_alpha:
        return True

    lowered = normalized.lower()
    legislative_cues = (
        "subject:",
        "approve",
        "adopt",
        "permit",
        "ordinance",
        "resolution",
        "hearing",
        "zoning",
        "budget",
        "contract",
        "amendment",
    )
    if any(cue in lowered for cue in legislative_cues):
        return False

    return first_alpha.islower()


def _is_procedural_noise_title(title: str) -> bool:
    """
    Return True for procedural placeholders that should not be treated as legislative items.

    Important: keep this precise. Broad substring matching (for example "approval")
    causes silent drops of substantive titles such as "Approval of Contract ...".
    """
    return lexicon_is_procedural_title(title, reject_enabled=AGENDA_PROCEDURAL_REJECT_ENABLED)


def _is_contact_or_letterhead_noise(title: str, desc: str = "") -> bool:
    """
    Return True for contact/letterhead metadata commonly mis-read as agenda items.
    """
    return lexicon_is_contact_or_letterhead_noise(_normalize_spaces(title), _normalize_spaces(desc))


def _llm_item_substance_score(title: str, desc: str = "") -> float:
    """
    Score how likely this looks like a substantive legislative item (0.0-1.0).
    """
    title_norm = _normalize_spaces(title)
    desc_norm = _normalize_spaces(desc)
    lowered = f"{title_norm} {desc_norm}".lower()
    score = 0.20

    if len(title_norm) >= AGENDA_MIN_TITLE_CHARS:
        score += 0.15

    if _is_procedural_noise_title(title_norm):
        score -= 0.45
    if _is_contact_or_letterhead_noise(title_norm, desc_norm):
        score -= 0.45

    legislative_terms = (
        "ordinance", "resolution", "contract", "budget", "zoning", "amendment",
        "plan", "program", "agreement", "hearing", "permit", "funding",
        "project", "recommendation", "policy", "appeal", "allocation",
    )
    if any(term in lowered for term in legislative_terms):
        score += 0.35

    action_terms = ("approve", "adopt", "authorize", "consider", "review", "receive", "vote")
    if any(term in lowered for term in action_terms):
        score += 0.15

    if len(desc_norm) >= AGENDA_MIN_SUBSTANTIVE_DESC_CHARS:
        score += 0.20

    return max(0.0, min(1.0, score))


def _should_accept_llm_item(item: dict, mode: str = "balanced") -> bool:
    """
    Acceptance gate for LLM-parsed items only.
    """
    title = _normalize_spaces(item.get("title", ""))
    desc = _normalize_spaces(item.get("description", ""))
    context = item.get("context") if isinstance(item, dict) else None
    if len(title) < AGENDA_MIN_TITLE_CHARS:
        return False
    if _is_procedural_noise_title(title):
        return False
    if _is_contact_or_letterhead_noise(title, desc):
        return False
    if _is_tabular_fragment(title, desc, context=context):
        return False

    threshold_map = {"recall": 0.28, "balanced": 0.45, "aggressive": 0.58}
    threshold = threshold_map.get((mode or "balanced").lower(), threshold_map["balanced"])
    score = _llm_item_substance_score(title, desc)

    # Why this branch exists: fallback parsers sometimes use short synthetic descriptions
    # like "Agenda section 2". We only enforce desc quality on direct LLM output.
    if len(desc) < AGENDA_MIN_SUBSTANTIVE_DESC_CHARS and score < threshold:
        return False
    return score >= threshold


def _dedupe_agenda_items_for_document(items: list[dict]) -> tuple[list[dict], int]:
    """
    Collapse near-duplicate agenda titles within one document (for example TOC + body).

    Why per-document only: cross-document fuzzy matching is incorrect and expensive.
    """
    if not items:
        return items, 0

    groups: list[list[tuple[int, dict]]] = []
    for idx, item in enumerate(items):
        title_key = _normalized_title_key(item.get("title", ""))
        if not title_key:
            continue
        matched = None
        for group_idx, group in enumerate(groups):
            ref_key = _normalized_title_key(group[0][1].get("title", ""))
            if fuzz.token_sort_ratio(title_key, ref_key) >= AGENDA_TOC_DEDUP_FUZZ:
                matched = group_idx
                break
        if matched is None:
            groups.append([(idx, item)])
        else:
            groups[matched].append((idx, item))

    winners: list[tuple[int, dict]] = []
    duplicates_removed = 0
    for group in groups:
        if len(group) > 1:
            duplicates_removed += len(group) - 1

        # Why we prefer higher pages: TOC entries often appear first; body pages carry context.
        winner = max(
            group,
            key=lambda pair: (
                int(pair[1].get("page_number") or 0),
                _llm_item_substance_score(pair[1].get("title", ""), pair[1].get("description", "")),
                len(_normalize_spaces(pair[1].get("description", ""))),
                -pair[0],
            ),
        )
        winners.append(winner)

    # Preserve stable extraction order among survivors.
    winners.sort(key=lambda pair: pair[0])
    return [item for _, item in winners], duplicates_removed


def _looks_like_attendance_boilerplate(line: str) -> bool:
    """
    Return True when a line is *probably* "how to attend / public comment / ADA" boilerplate.

    Why this exists:
    Agenda PDFs often start with participation instructions (Zoom links, dial-in, ADA info).
    If we feed those lines into the LLM, the model tends to "summarize" the boilerplate.
    """
    if not line:
        return False

    lowered = line.strip().lower()

    # URLs and contact lines are almost never meaningful "meeting content".
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", lowered):
        return True

    # Phone numbers and meeting IDs show up in dial-in instructions.
    if re.search(r"\b\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}\b", lowered):
        return True
    if re.search(r"\bmeeting id\b|\bwebinar id\b|\bpasscode\b", lowered):
        return True

    # Common attendance / participation terms.
    boilerplate_fragments = (
        "zoom",
        "webinar",
        "teleconference",
        "livestream",
        "live stream",
        "register in advance",
        "meeting link",
        "join by phone",
        "dial",
        "unmute",
        "raise hand",
        "conference room",
        "virtual meeting",
        "meeting will be held",
        "public comment",
        "public participation",
        "speakers will be",
        "called to speak",
        "limit your remarks",
        "time allotted",
        "written communications",
        "options to observe",
        "options to participate",
        "attend in person",
        "appear in person",
        "members of the public",
        "submit comments",
        "email comments",
        "e-mail comments",
        "communication access",
        "americans with disabilities act",
        "ada",
        "accommodation",
        "auxiliary aids",
        "interpreters",
        "disability-related",
    )
    return any(frag in lowered for frag in boilerplate_fragments)


def _looks_like_agenda_segmentation_boilerplate(line: str) -> bool:
    """
    Return True when a line is *probably* boilerplate that should not become an agenda item.

    Why this exists:
    Agenda segmentation is more sensitive than summarization. In many PDFs the
    participation/teleconference/COVID/ADA section is numbered, which can look
    like "real items" to simple numbered-line heuristics.
    """
    if not line:
        return False

    lowered = (line or "").strip().lower()
    compact = re.sub(r"[^a-z0-9]+", "", lowered)

    # Reuse the summarization boilerplate filter first.
    if _looks_like_attendance_boilerplate(lowered):
        return True

    # COVID-era and remote-meeting legal/policy notices.
    covid_fragments = (
        "covid",
        "covid-19",
        "coronavirus",
        "state of emergency",
        "executive order",
        "governor newsom",
        "order no-",
        "order no.",
    )
    if any(frag in lowered for frag in covid_fragments):
        return True
    covid_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in covid_fragments)
    if any(frag and frag in compact for frag in covid_compact):
        return True

    # Remote meeting platform mechanics and browser requirements.
    platform_fragments = (
        "join the webinar",
        "join by phone",
        "please read the following instructions",
        "please read the instructions carefully",
        "instructions carefully",
        "you will be asked to enter",
        "enter an email address",
        "confirmation email",
        "raise hand",
        "unmute",
        "mute",
        "last four digits",
        "internet browser",
        "browser",
        "microsoft edge",
        "internet explorer",
        "chrome",
        "firefox",
        "safari",
        "h.323",
        "sip",
        "passcode",
        "meeting id",
        "webinar id",
        "registration",
        "register",
    )
    if any(frag in lowered for frag in platform_fragments):
        return True
    platform_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in platform_fragments)
    if any(frag and frag in compact for frag in platform_compact):
        return True

    # Registration templates often include privacy/identity instructions that are not agenda topics.
    if "email address" in lowered:
        return True
    if "will not be disclosed" in lowered:
        return True
    if "connect to the meeting" in lowered:
        return True
    if "you may enter" in lowered and ("designation" in lowered or "resident" in lowered):
        return True

    # Some templates include lists of teleconference endpoints like:
    # "144.110 (Amsterdam Netherlands)" or "140.110 (Germany)".
    # These are participation mechanics, not agenda topics.
    if _looks_like_teleconference_endpoint_line(lowered):
        return True

    # ADA / accessibility wording in many agenda templates.
    accessibility_fragments = (
        "communication access",
        "disability",
        "accommodation",
        "auxiliary aids",
        "interpreters",
        "americans with disabilities act",
        "ada",
    )
    if any(frag in lowered for frag in accessibility_fragments):
        return True
    accessibility_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in accessibility_fragments)
    if any(frag and frag in compact for frag in accessibility_compact):
        return True

    # Broadcast/streaming availability notices and similar "how to watch" headers.
    # These are often visually prominent and get misclassified as agenda items.
    broadcast_fragments = (
        "public advisory",
        "live captioned",
        "captioned broadcast",
        "captioned broadcasts",
        "broadcasts of council meetings",
        "council meetings are available",
        "b-tv",
        "channel 33",
        "kpfa",
        "kpbf",  # occasionally OCR'd
        "radio 89.3",
        "internet video stream",
        "video stream",
        "webcast",
        "livestream",
        "live stream",
    )
    if any(frag in lowered for frag in broadcast_fragments):
        return True
    broadcast_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in broadcast_fragments)
    if any(frag and frag in compact for frag in broadcast_compact):
        return True

    # Hybrid meeting participation blurbs (not substantive agenda items).
    hybrid_fragments = (
        "hybrid model",
        "virtual attendance",
        "in-person and virtual",
        "attend this meeting",
        "attend the meeting remotely",
        "meeting will be conducted in a hybrid",
        "to access the meeting",
        "to access the meeting remotely",
        "join from a pc",
        "please use this url",
    )
    if any(frag in lowered for frag in hybrid_fragments):
        return True
    hybrid_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in hybrid_fragments)
    if any(frag and frag in compact for frag in hybrid_compact):
        return True

    # Public records / speaker-card notice blocks are template legal language, not agenda topics.
    notice_fragments = (
        "important notice",
        "any writings or documents provided to a majority",
        "supplemental material to the agendized item",
        "agendized item",
        "made publicly available on the city website",
        "wish to address the planning commission",
        "speaker request card",
        "when you are called, proceed to the podium",
        "any other item not on the agenda",
        "comments to three",
        "for questions on any items in the agenda",
        "meeting agendas and writings distributed",
        "described in the notice",
        "consideration of that item",
        "request card located in front",
        "prior to discussion of the",
        "proceed to the podium",
        "address the planning commission",
        "government code section 84308",
        "levine act",
        "parties to a proceeding involving a license, permit, or other",
        "in accordance with the authority in me vested",
        "i do hereby call the berkeley city council",
        "presiding officer may remove",
        "disrupting the meeting",
        "failure to cease their behavior",
        "this proclamation serves as the official agenda",
        "cause personal notice to be given",
    )
    if any(frag in lowered for frag in notice_fragments):
        return True
    notice_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in notice_fragments)
    if any(frag and frag in compact for frag in notice_compact):
        return True

    # Prominent cover/heading blocks that are not agenda items.
    heading_fragments = (
        "annotated agenda",
        "special meeting of the",
        "calling a special meeting",
        "proclamation",
        "planning commission agenda",
    )
    if any(frag in lowered for frag in heading_fragments):
        return True
    heading_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in heading_fragments)
    if any(frag and frag in compact for frag in heading_compact):
        return True

    # Presentation/polling app instructions are not agenda items.
    poll_fragments = (
        "mentimeter",
        "slido",
        "poll",
        "survey",
        "enter code",
        "mobile device",
        "qr code",
    )
    if any(frag in lowered for frag in poll_fragments):
        return True
    poll_compact = tuple(re.sub(r"[^a-z0-9]+", "", frag) for frag in poll_fragments)
    if any(frag and frag in compact for frag in poll_compact):
        return True

    return False


def _looks_like_teleconference_endpoint_line(line: str) -> bool:
    """
    Return True for short "endpoint list" lines that show up in teleconference instructions.

    Why this exists:
    Some meeting templates list H.323/SIP endpoints by region, e.g. "144.110 (Amsterdam Netherlands)".
    Those lines are often numbered, which confuses simple agenda segmentation heuristics.
    """
    if not line:
        return False

    lowered = (line or "").strip().lower()
    m = re.match(r"^\s*(\d{2,3})\.(\d{2,3})(?:\.(\d{1,3}))?(?:\.(\d{1,3}))?\s*(.*)$", lowered)
    if not m:
        return False

    # Reduce false positives for genuine section numbers like "2.1" or "12.3".
    a = int(m.group(1))
    b = int(m.group(2))
    if a < 20 or b < 20:
        return False

    tail = (m.group(5) or "").strip()

    # Some PDFs truncate or wrap, so tolerate missing closing parens.
    if not tail:
        return True
    if tail.startswith("("):
        return True
    return False


def _looks_like_sub_marker_title(value: str) -> bool:
    """
    Detect likely nested list markers (A., 1a., i.) that often represent child rows.
    """
    title = _normalize_spaces(value)
    return bool(re.match(r"^(?:[A-Z]\.|[0-9]{1,2}[a-z]\.|[ivxlcdm]+\.)\s+", title, flags=re.IGNORECASE))


def _is_tabular_fragment(title: str, desc: str = "", context: dict | None = None) -> bool:
    """
    Detect flattened table/list rows that should not be promoted to top-level agenda items.

    Primary signal:
    - low alpha-character density on short text.

    Secondary signals (weak alone):
    - column-like whitespace artifacts
    - sub-marker under active parent context
    - row-like token shape (number/symbol heavy, low verb density)
    """
    raw_title = title or ""
    raw_desc = desc or ""
    raw_combined = f"{raw_title} {raw_desc}".strip()
    combined = _normalize_spaces(raw_combined)
    if not combined:
        return False
    if len(combined) > 180:
        return False

    total_chars = len(combined)
    alpha_chars = sum(1 for c in combined if c.isalpha())
    alpha_density = (alpha_chars / total_chars) if total_chars else 1.0

    tokens = [t for t in re.split(r"\s+", combined.lower()) if t]
    number_symbol_ratio = 0.0
    if tokens:
        number_symbol_tokens = sum(1 for t in tokens if re.search(r"[0-9$%/|#]", t))
        number_symbol_ratio = number_symbol_tokens / len(tokens)

    # Primary signal should be driven by low alpha density + clearly row-like token makeup.
    strong_primary = len(combined) <= 150 and alpha_density < 0.60 and number_symbol_ratio >= 0.25

    secondary_signals = 0
    if "\t" in raw_combined or re.search(r" {3,}", raw_combined):
        secondary_signals += 1

    has_active_parent = bool((context or {}).get("has_active_parent"))
    if has_active_parent and _looks_like_sub_marker_title(raw_title):
        secondary_signals += 1

    if tokens:
        number_symbol_tokens = sum(1 for t in tokens if re.search(r"[0-9$%/|#]", t))
        if (number_symbol_tokens / len(tokens)) >= 0.35:
            secondary_signals += 1
        verb_like_tokens = (
            "approve", "adopt", "authorize", "consider", "review", "receive", "conduct",
            "hold", "amend", "create", "repeal", "establish", "select",
        )
        if len(tokens) >= 5 and not any(v in " ".join(tokens) for v in verb_like_tokens):
            secondary_signals += 1

    if strong_primary:
        return True
    if has_active_parent and secondary_signals >= 2:
        return True
    if secondary_signals >= 3 and len(combined) <= 120:
        return True
    return False


def _looks_like_end_marker_line(line: str) -> bool:
    lowered = _normalize_spaces(line).lower()
    if not lowered:
        return False
    marker_patterns = (
        r"^adjournment$",
        r"^attest\b",
        r"^notice concerning your legal rights\b",
        r"\bin witness whereof\b",
        r"\bofficial seal\b",
        r"public notice.*official agenda",
    )
    return any(re.search(pattern, lowered) for pattern in marker_patterns)


def _should_stop_after_marker(current_line: str, lookahead_window: str) -> bool:
    """
    Composite end-of-agenda detector.

    Adjournment alone is insufficient; we require legal/attestation tail evidence.
    """
    line = _normalize_spaces(current_line).lower()
    window = (lookahead_window or "").lower()
    if not line:
        return False

    legal_tail_markers = (
        "attest",
        "in witness whereof",
        "official seal",
        "notice concerning your legal rights",
        "cause personal notice",
        "city clerk",
        "date:",
        "public notice",
    )
    legal_hits = sum(1 for marker in legal_tail_markers if marker in window)

    substantive_signals = (
        "subject:",
        "recommendation:",
        "action calendar",
        "financial implications",
        "conduct a public hearing",
    )
    has_substantive_after = any(signal in window for signal in substantive_signals)

    if "adjournment" in line:
        return legal_hits >= 2 and not has_substantive_after
    return legal_hits >= 2


def _strip_summary_output_boilerplate(summary: str) -> str:
    """
    Backwards-compatible wrapper for summary cleanup.

    New behavior:
    Summaries are normalized into a BLUF-first, plain-text format so the UI never
    needs to render Markdown and never shows teleconference boilerplate.
    """
    return summary


def _strip_summary_boilerplate(text: str) -> str:
    """
    Remove common meeting boilerplate that pollutes both summaries and topic extraction.

    This is intentionally heuristic and conservative:
    - We drop lines that are overwhelmingly "how to attend / Zoom / dial-in / ADA" instructions.
    - If stripping removes too much content, the caller should fall back to the original text.
    """
    if not text:
        return text

    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _looks_like_attendance_boilerplate(line):
            continue
        lines.append(line)

    # De-dupe repeated instruction lines (common in some agenda templates).
    lines = _dedupe_lines_preserve_order(lines)
    return "\n".join(lines).strip()

def _strip_markdown_emphasis(text: str) -> str:
    """
    Remove common Markdown emphasis markers from model output.

    Why this exists:
    The UI renders summaries as plain text. If the model emits Markdown, users see
    raw markers like "**Agenda:**" instead of formatted text.
    """
    if not text:
        return text
    # Keep this conservative: remove only the markers, preserve the inner text.
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def _first_sentence(value: str) -> str:
    """
    Return the first sentence-like chunk (or the whole string if no punctuation).

    This keeps BLUF short and predictable.
    """
    if not value:
        return value
    value = value.strip()
    match = re.search(r"^(.+?[\.!\?])(\s|$)", value)
    return (match.group(1) if match else value).strip()


def _cap_words(value: str, max_words: int = 30) -> str:
    if not value:
        return value
    words = value.strip().split()
    if len(words) <= max_words:
        return value.strip()
    return " ".join(words[:max_words]).rstrip(".,;:") + "."


def _normalize_summary_output_to_bluf(summary: str, source_text: str = "") -> str:
    """
    Normalize summary output into a BLUF-first, plain-text format:

    BLUF: <one-sentence takeaway>.
    - <detail bullet>
    - <detail bullet>

    Requirements:
    - no Markdown markers
    - no teleconference/ADA/how-to-attend boilerplate
    - 3-7 bullets when possible
    """
    if not summary:
        return summary

    # Token-based grounding uses the same threshold as the worker-level guardrail.
    # We apply it here to drop obviously unsupported bullets before they hit the DB/UI.
    from pipeline.config import SUMMARY_GROUNDING_MIN_COVERAGE

    WORD_RE = re.compile(r"[a-z0-9']+")
    STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
        "it", "of", "on", "or", "that", "the", "to", "was", "were", "with", "this",
        "these", "those", "will", "would", "can", "could", "may", "might",
    }

    def _tokenize(value: str) -> list[str]:
        return WORD_RE.findall((value or "").lower())

    source_tokens = set(_tokenize(source_text or ""))
    source_prefixes = {tok[:5] for tok in source_tokens if len(tok) >= 5}

    def _coverage(claim: str) -> float:
        claim_tokens = [t for t in _tokenize(claim) if len(t) >= 3 and t not in STOPWORDS]
        if not claim_tokens:
            return 1.0
        matched = 0
        for t in claim_tokens:
            if t in source_tokens:
                matched += 1
                continue
            if len(t) >= 5 and t[:5] in source_prefixes:
                matched += 1
                continue
        return matched / len(claim_tokens)

    raw_lines = [ln.rstrip() for ln in summary.splitlines()]
    cleaned_lines = []
    for raw in raw_lines:
        line = (raw or "").strip()
        if not line:
            continue

        lowered = line.lower()
        # Drop preambles like "Here's a summary..." (models often ignore "no extra text").
        if (lowered.startswith("here") and "summary" in lowered) or ("executive summary" in lowered):
            continue
        if lowered.startswith("summary of the meeting"):
            continue

        line = _strip_markdown_emphasis(line).strip()

        # Strip common bullet markers so the output stays consistent.
        # Note: we re-add bullets later using "- ".
        line = re.sub(r"^\s*[\*\-\u2022]+\s*", "", line).strip()
        if not line:
            continue

        # Remove any remaining leading numbering like "1." or "1)".
        line = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", line).strip()
        if not line:
            continue

        if _looks_like_attendance_boilerplate(line):
            continue

        cleaned_lines.append(line)

    cleaned_lines = _dedupe_lines_preserve_order(cleaned_lines)
    if not cleaned_lines:
        # Fall back to quoting the extracted text so the grounding gate can pass.
        # This avoids saving hallucinated content when the model output is unusable.
        snippet = re.sub(r"\[PAGE\s+\d+\]\s*", " ", (source_text or ""), flags=re.IGNORECASE).strip()
        snippet = " ".join(snippet.split())
        if snippet:
            return f"BLUF: Summary unavailable from extracted text.\n- {snippet[:200]}"
        return "BLUF: Summary unavailable from extracted text.\n- Summary unavailable."

    bluf_text = None
    bullets = []
    for line in cleaned_lines:
        if line.lower().startswith("bluf:"):
            bluf_text = line.split(":", 1)[1].strip()
            continue
        bullets.append(line)

    if not bluf_text:
        # Use first bullet/line as the seed for BLUF.
        seed = bullets[0] if bullets else cleaned_lines[0]
        bluf_text = seed

    bluf_text = _cap_words(_first_sentence(bluf_text), max_words=30)
    if bluf_text and not bluf_text.endswith((".", "!", "?")):
        bluf_text = bluf_text.rstrip(".,;:") + "."

    # Drop boilerplate again in case BLUF seed contained it.
    if _looks_like_attendance_boilerplate(bluf_text):
        bluf_text = "Key meeting takeaway is unclear from extracted text."

    # Bound bullet count.
    bullets = [b for b in bullets if b and not _looks_like_attendance_boilerplate(b)]
    bullets = _dedupe_lines_preserve_order(bullets)
    # Drop unsupported/paraphrased bullets; we'll fall back to source lines if this removes too much.
    if source_tokens:
        bullets = [b for b in bullets if _coverage(b) >= SUMMARY_GROUNDING_MIN_COVERAGE]
    bullets = bullets[:7]

    # Try to keep at least 3 bullets when the model gave enough content.
    if len(bullets) < 3 and len(cleaned_lines) >= 3:
        for extra in cleaned_lines:
            if extra.lower().startswith("bluf:"):
                continue
            if extra in bullets:
                continue
            if _looks_like_attendance_boilerplate(extra):
                continue
            bullets.append(extra)
            if len(bullets) >= 3:
                break
        if source_tokens:
            bullets = [b for b in bullets if _coverage(b) >= SUMMARY_GROUNDING_MIN_COVERAGE]
        bullets = bullets[:7]

    # If the model didn't produce usable bullets, fall back to quoting salient source text.
    #
    # Why: this keeps output grounded (we only show what exists in the extracted text),
    # and avoids "blocked_ungrounded" when the model returns vague headings.
    if len(bullets) == 0 and source_text:
        text = source_text or ""
        # Break up single-line dumps by making page markers act like separators.
        text = re.sub(r"\[PAGE\s+\d+\]\s*", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).replace(" \n ", "\n")

        raw_chunks = []
        for raw in text.splitlines():
            ln = raw.strip()
            if not ln:
                continue
            # Split common agenda item numbering when extraction flattens everything.
            parts = re.split(r"\b\d+\.\s+", ln)
            for part in parts:
                part = part.strip()
                if part:
                    raw_chunks.append(part)

        candidates = []
        for chunk in raw_chunks:
            if _looks_like_attendance_boilerplate(chunk):
                continue
            if len(chunk) < 12:
                continue
            candidates.append(chunk)
            if len(candidates) >= 7:
                break

        candidates = _dedupe_lines_preserve_order(candidates)
        bullets = candidates[:7]

        # Absolute fallback: quote a short snippet from the source so the grounding gate passes.
        if len(bullets) == 0:
            snippet = re.sub(r"\[PAGE\s+\d+\]\s*", " ", (source_text or ""), flags=re.IGNORECASE).strip()
            snippet = " ".join(snippet.split())
            if snippet:
                bullets = [snippet[:200]]

    if len(bullets) == 0:
        bullets = ["Summary unavailable from extracted text."]

    # Re-emit canonical format (plain text).
    out_lines = [f"BLUF: {bluf_text}".strip()]
    for b in bullets:
        out_lines.append(f"- {b.strip()}")
    return "\n".join(out_lines).strip()

def prepare_summary_prompt(text: str, doc_kind: str = "unknown") -> str:
    """
    Build a summarization prompt that matches the *document type*.

    Why this matters:
    Some cities publish agenda PDFs without minutes PDFs. If we summarize an agenda
    using a "minutes" prompt, the output will focus on attendance/teleconference
    boilerplate and look incorrect.
    """
    kind = normalize_summary_doc_kind(doc_kind)
    if kind not in _SUMMARY_DOC_KINDS:
        kind = "unknown"

    # 1) Clean input to avoid "how to attend" text dominating the summary.
    safe_text = (text or "")[:LLM_SUMMARY_MAX_TEXT]
    stripped = _strip_summary_boilerplate(safe_text)
    # If stripping leaves very little, keep the original so we don't summarize nothing.
    if stripped and len(stripped) >= max(200, int(0.2 * len(safe_text))):
        safe_text = stripped

    if kind == "minutes":
        instruction = (
            "Write a plain-text executive summary of these meeting minutes. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on decisions, actions taken, and vote outcomes.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    elif kind == "agenda":
        instruction = (
            "Write a plain-text executive summary of this meeting agenda. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on the main scheduled items and expected actions.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    else:
        instruction = (
            "Write a plain-text executive summary of this meeting document. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )

    return (
        "<start_of_turn>user\n"
        f"{instruction}\n"
        "Return only the BLUF line and the bullet lines. No extra text.\n"
        f"{safe_text}<end_of_turn>\n"
        "<start_of_turn>model\n"
    )


def _coerce_agenda_summary_item(item, idx: int = 0) -> dict:
    """
    Normalize agenda summary input into a structured record.
    """
    if isinstance(item, dict):
        title = _normalize_spaces(item.get("title", ""))
        desc = _normalize_spaces(item.get("description", ""))
        classification = _normalize_spaces(item.get("classification", ""))
        result = _normalize_spaces(item.get("result", ""))
        try:
            page_number = int(item.get("page_number") or 0)
        except Exception:
            page_number = 0
    else:
        title, desc = _split_agenda_summary_item(_normalize_spaces(item or ""))
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
    """
    Pull short money references to ground "impact" language in civic summaries.
    """
    matches = re.findall(r"\$\s?\d[\d,]*(?:\.\d{2})?(?:\s*(?:million|billion|thousand|m|k))?", text or "", flags=re.IGNORECASE)
    seen = set()
    out = []
    for m in matches:
        key = m.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(m.strip())
        if len(out) >= 5:
            break
    return out


def _agenda_items_source_text(items: list[dict]) -> str:
    """
    Serialize structured agenda items for lexical grounding checks.
    """
    lines = []
    for it in items:
        bits = [f"Title: {it.get('title', '')}"]
        if it.get("description"):
            bits.append(f"Description: {it['description']}")
        if it.get("classification"):
            bits.append(f"Classification: {it['classification']}")
        if it.get("result"):
            bits.append(f"Result: {it['result']}")
        if it.get("page_number"):
            bits.append(f"Page: {it['page_number']}")
        lines.append(" | ".join(bits))
    return "\n".join(lines).strip()


def _build_agenda_summary_scaffold(
    items: list[dict],
    truncation_meta: dict | None = None,
    profile: str = "decision_brief",
) -> dict:
    """
    Deterministic scaffold for agenda brief synthesis.
    """
    total = len(items)
    titles = [it.get("title", "") for it in items if it.get("title")]
    combined = " ".join(
        [f"{it.get('title', '')} {it.get('description', '')} {it.get('result', '')}" for it in items]
    ).strip()
    money_refs = _extract_money_snippets(combined)

    bluf = f"Agenda includes {total} substantive item{'s' if total != 1 else ''}."
    if money_refs:
        bluf += f" Mentioned monetary figures include {', '.join(money_refs[:2])}."

    top_actions = []
    for it in items[: max(3, min(6, AGENDA_SUMMARY_MAX_BULLETS))]:
        title = _normalize_spaces(it.get("title", ""))
        if not title:
            continue
        desc = _normalize_spaces(it.get("description", ""))
        page = it.get("page_number") or 0
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
    if money_refs or any(w in lowered for w in ("budget", "fund", "appropriation", "contract", "grant", "cost")):
        potential_impacts["budget"] = "Budget/funding considerations appear likely based on the agenda language."
    if any(w in lowered for w in ("ordinance", "resolution", "zoning", "amendment", "permit", "policy")):
        potential_impacts["policy"] = "Policy/regulatory changes may be considered based on listed agenda items."
    if any(w in lowered for w in ("hearing", "appeal", "review", "consider", "adopt", "approve")):
        potential_impacts["process"] = "The meeting is positioned for formal review/consideration actions."

    unknowns = []
    if not money_refs:
        unknowns.append("Specific dollar amounts are not clearly disclosed across the listed items.")
    if not any(_normalize_spaces(it.get("result", "")) for it in items):
        unknowns.append("Vote outcomes are not provided in agenda-stage records.")
    if truncation_meta and (truncation_meta.get("items_truncated") or 0) > 0:
        unknowns.append(
            f"Summary generated from first {truncation_meta.get('items_included', 0)} of {truncation_meta.get('items_total', 0)} agenda items due to context limits."
        )

    single_item_mode = bool(total == 1 and AGENDA_SUMMARY_SINGLE_ITEM_MODE == "deep_brief")
    why_this_matters = ""
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
    """
    Build a constrained decision-brief prompt from structured agenda items.
    """
    title = (meeting_title or "").strip()
    date = (meeting_date or "").strip()
    header_parts = [p for p in [title, date] if p]
    header = " - ".join(header_parts) if header_parts else "Meeting agenda"

    lines = []
    for i, it in enumerate(items):
        title_txt = _normalize_spaces(it.get("title", ""))
        desc_txt = _normalize_spaces(it.get("description", ""))
        class_txt = _normalize_spaces(it.get("classification", ""))
        result_txt = _normalize_spaces(it.get("result", ""))
        page = it.get("page_number") or 0
        lines.append(
            f"{i+1}. Title: {title_txt} | Description: {desc_txt or '(none)'} | "
            f"Classification: {class_txt or '(none)'} | Result: {result_txt or '(none)'} | Page: {page or '(unknown)'}"
        )
    items_block = "\n".join(lines)

    top_actions_seed = "\n".join([f"- {v}" for v in scaffold.get("top_actions", [])]) or "- (none)"
    impacts = scaffold.get("potential_impacts", {})
    unknowns_seed = "\n".join([f"- {v}" for v in scaffold.get("unknowns", [])]) or "- (none)"
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
    structured = [_coerce_agenda_summary_item(item, idx=i) for i, item in enumerate(items or [])]
    scaffold = _build_agenda_summary_scaffold(structured, truncation_meta=None, profile=AGENDA_SUMMARY_PROFILE)
    return _prepare_structured_agenda_items_summary_prompt(
        meeting_title=meeting_title,
        meeting_date=meeting_date,
        items=structured,
        scaffold=scaffold,
        truncation_meta=None,
    )


def _normalize_bullets_to_dash(text: str) -> str:
    """
    Normalize bullet markers to "- " (plain text).

    Why:
    The UI does not render Markdown. We still want consistent bullet output.
    """
    if not text:
        return ""
    text = re.sub(r"(?m)^\\s*[\\*\\u2022]\\s+", "- ", text)
    text = re.sub(r"(?m)^\\s+-\\s+", "- ", text)
    return text


def _agenda_items_summary_is_too_short(text: str) -> bool:
    """
    Decide whether a model agenda summary is too short / low-utility.

    We prefer returning a deterministic fallback over storing a useless model output.
    """
    if not text:
        return True
    t = text.strip()
    if len(t) < 220:
        return True
    lower = t.lower()
    required_sections = ("why this matters:", "top actions:", "potential impacts:", "unknowns:")
    if any(section not in lower for section in required_sections):
        return True
    bullet_lines = [ln for ln in t.splitlines() if ln.strip().startswith("- ")]
    if len(bullet_lines) < 5:
        return True
    top_actions = 0
    in_top_actions = False
    for ln in t.splitlines():
        stripped = ln.strip().lower()
        if stripped == "top actions:":
            in_top_actions = True
            continue
        if stripped.endswith(":") and stripped != "top actions:":
            in_top_actions = False
        if in_top_actions and ln.strip().startswith("- "):
            top_actions += 1
    if top_actions < 2:
        return True
    return False


def _ensure_single_item_decision_section(text: str, scaffold: dict) -> str:
    """
    For single-item deep briefs, guarantee a 'Decision/action requested' section exists.
    """
    value = (text or "").strip()
    if not value:
        return value
    if not scaffold.get("single_item_mode"):
        return value
    if re.search(r"(?im)^decision/action requested:\s*$", value):
        return value
    actions = scaffold.get("top_actions", [])
    default_line = actions[0] if actions else "The agenda focuses on one primary action item."
    block = f"Decision/action requested:\n- {default_line}\n"
    if re.search(r"(?im)^top actions:\s*$", value):
        return re.sub(r"(?im)^top actions:\s*$", block + "Top actions:", value, count=1)
    return value + "\n" + block


def _deterministic_agenda_items_summary(
    items,
    max_bullets: int = 25,
    truncation_meta: dict | None = None,
) -> str:
    """
    Deterministic fallback summary for agendas (sectioned decision brief).
    """
    structured = [_coerce_agenda_summary_item(item, idx=i) for i, item in enumerate(items or [])]
    scaffold = _build_agenda_summary_scaffold(structured, truncation_meta=truncation_meta)
    shown = scaffold.get("top_actions", [])[:max_bullets]

    out_lines = [f"BLUF: {scaffold.get('bluf_seed', 'Agenda summary unavailable.')}"]
    out_lines.append("Why this matters:")
    out_lines.append(f"- {scaffold.get('why_this_matters', 'This agenda includes planned council actions.')}")
    out_lines.append("Top actions:")
    if shown:
        out_lines.extend([f"- {it}" for it in shown])
    else:
        out_lines.append("- No substantive actions were retained after filtering.")
    if scaffold.get("single_item_mode"):
        out_lines.append("Decision/action requested:")
        out_lines.append(f"- {(shown[0] if shown else 'The agenda focuses on one primary action item.')}")

    impacts = scaffold.get("potential_impacts", {})
    out_lines.append("Potential impacts:")
    out_lines.append(f"- Budget: {impacts.get('budget', 'Not clearly stated.')}")
    out_lines.append(f"- Policy: {impacts.get('policy', 'Not clearly stated.')}")
    out_lines.append(f"- Process: {impacts.get('process', 'Not clearly stated.')}")

    out_lines.append("Unknowns:")
    for unknown in scaffold.get("unknowns", []):
        out_lines.append(f"- {unknown}")
    return "\n".join(out_lines).strip()


def _split_agenda_summary_item(value: str) -> tuple[str, str]:
    """
    Split a serialized agenda item into (title, description) for summary filtering.
    """
    text = _normalize_spaces(value)
    if not text:
        return "", ""
    if " - " in text:
        left, right = text.split(" - ", 1)
        return left.strip(), right.strip()
    return text, ""


def _should_drop_from_agenda_summary(item_text: str) -> bool:
    """
    Residual summary safety-net:
    drop only when title looks like boilerplate/fragment AND description is short.
    """
    title, desc = _split_agenda_summary_item(item_text)
    if not title:
        return True
    title_looks_noisy = (
        _looks_like_agenda_segmentation_boilerplate(title)
        or _is_procedural_noise_title(title)
        or _is_contact_or_letterhead_noise(title, desc)
        or _is_probable_line_fragment_title(title)
    )
    if not title_looks_noisy:
        return False
    return len(_normalize_spaces(desc)) < AGENDA_MIN_SUBSTANTIVE_DESC_CHARS

def _strip_llm_acknowledgements(text: str) -> str:
    """
    Remove common "acknowledgement" / compliance preambles from LLM output.

    Why this exists:
    Even with good prompts, small instruction-tuned models sometimes begin with
    "Okay, I understand..." which is UI-noise and reduces trust.
    """
    if not text:
        return ""

    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue

        lowered = ln.lower()
        # If the model crams the acknowledgement and the BLUF onto one line,
        # keep the BLUF portion instead of dropping the entire line.
        if "bluf:" in lowered:
            idx = lowered.index("bluf:")
            return ln[idx:].strip() + ("\n" + "\n".join(lines[i + 1 :]).strip() if (i + 1) < len(lines) else "")
        # Keep this list small and generic; we only strip at the start.
        if (
            lowered.startswith("okay")
            or lowered.startswith("sure")
            or lowered.startswith("certainly")
            or lowered.startswith("got it")
            or lowered.startswith("understood")
            or "i understand" in lowered
            or lowered.startswith("i will")
            or lowered.startswith("i'll")
        ):
            i += 1
            continue

        break

    return "\n".join(lines[i:]).strip()


def _normalize_model_agenda_summary_output(text: str, scaffold: dict) -> str:
    """
    Normalize model output into Town Council's plain-text decision-brief contract.
    """
    cleaned = _strip_markdown_emphasis(text).strip()
    cleaned = _strip_llm_acknowledgements(cleaned).strip()
    cleaned = _normalize_bullets_to_dash(cleaned).strip()
    if cleaned and not cleaned.startswith("BLUF:"):
        cleaned = f"BLUF: {scaffold.get('bluf_seed', 'Agenda summary.')}"
    return _ensure_single_item_decision_section(cleaned, scaffold)


def _agenda_summary_helpers() -> AgendaSummaryHelpers:
    """
    Keep agenda-summary orchestration separate while LocalAI still owns provider policy.
    """
    return AgendaSummaryHelpers(
        coerce_item=_coerce_agenda_summary_item,
        should_drop_item=_should_drop_from_agenda_summary,
        build_scaffold=lambda items, truncation_meta: _build_agenda_summary_scaffold(
            items,
            truncation_meta=truncation_meta,
            profile=AGENDA_SUMMARY_PROFILE,
        ),
        build_prompt=_prepare_structured_agenda_items_summary_prompt,
        source_text=_agenda_items_source_text,
        normalize_output=_normalize_model_agenda_summary_output,
        deterministic_summary=_deterministic_agenda_items_summary,
        is_too_short=_agenda_items_summary_is_too_short,
    )

def _agenda_extraction_helpers() -> AgendaExtractionHelpers:
    """
    Keep extraction heuristics reusable while LocalAI still owns provider behavior.
    """
    return AgendaExtractionHelpers(
        normalize_spaces=_normalize_spaces,
        is_probable_line_fragment_title=_is_probable_line_fragment_title,
        is_procedural_noise_title=_is_procedural_noise_title,
        is_contact_or_letterhead_noise=_is_contact_or_letterhead_noise,
        looks_like_teleconference_endpoint_line=_looks_like_teleconference_endpoint_line,
        looks_like_agenda_segmentation_boilerplate=_looks_like_agenda_segmentation_boilerplate,
        is_tabular_fragment=_is_tabular_fragment,
        should_accept_llm_item=_should_accept_llm_item,
        dedupe_agenda_items_for_document=_dedupe_agenda_items_for_document,
        looks_like_end_marker_line=_looks_like_end_marker_line,
        should_stop_after_marker=_should_stop_after_marker,
    )


def parse_llm_agenda_items(llm_text: str) -> list[dict]:
    """
    Backwards-compatible wrapper for agenda parser tests and diagnostic callers.
    """
    return parse_llm_agenda_items_impl(llm_text)


def iter_fallback_paragraphs(page_content: str) -> list[str]:
    """
    Backwards-compatible wrapper for fallback paragraph diagnostics.
    """
    return iter_fallback_paragraphs_impl(page_content)


class LocalAI:
    """
    The 'Brain' of our application.

    Uses a singleton pattern to keep the model loaded in RAM *per Python process*.
    What's a singleton? It means only ONE instance of this class exists in a given process.
    Why? Loading the AI model takes ~5 seconds and uses ~500MB RAM. We don't want
    to load it multiple times!

    Important architecture note:
    Celery prefork/multiprocessing spawns multiple worker processes. Processes do not
    share memory, so each process would load its own model copy unless guarded.
    """
    _instance = None  # Stores the single instance
    _lock = threading.Lock()  # Prevents race conditions when multiple threads try to create the instance

    def __new__(cls):
        """
        This special method controls how new instances are created.
        Instead of creating a new instance every time, we return the same one.
        """
        # First check: Is there already an instance? (fast path, no lock needed)
        if cls._instance is None:
            # Multiple threads might reach here at the same time, so we need a lock
            with cls._lock:
                # Second check: Now that we have the lock, double-check no one else created it
                if cls._instance is None:
                    cls._instance = super(LocalAI, cls).__new__(cls)
                    cls._instance.llm = None  # Initialize the model as None (we'll load it later)
                    cls._instance._provider = None
                    cls._instance._provider_backend = None
        return cls._instance

    def _get_provider(self):
        backend = (LOCAL_AI_BACKEND or "http").strip().lower()
        if backend not in {"inprocess", "http"}:
            backend = "http"
        # Why this branch exists: backend mode is env-driven and can change between test runs.
        if self._provider is None or self._provider_backend != backend:
            if backend == "http":
                self._provider = HttpInferenceProvider()
            else:
                self._provider = InProcessLlamaProvider(self)
            self._provider_backend = backend
        return self._provider

    def _log_provider_failure(self, operation_label: str, error: Exception) -> None:
        logger.error("%s failed: %s", operation_label, error)

    def _call_provider_text_or_none(
        self,
        provider_call: Callable[[], str | None],
        *,
        operation_label: str,
    ) -> str | None:
        try:
            return provider_call()
        except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as error:
            self._log_provider_failure(operation_label, error)
            return None
        except Exception as error:
            self._log_provider_failure(operation_label, error)
            return None

    def _load_model(self):
        """
        Loads the AI model from disk into memory.

        This is wrapped in a lock because:
        1. Loading takes several seconds
        2. If two threads try to load simultaneously, we'd waste RAM and cause errors
        3. The lock ensures only ONE thread loads the model, others wait
        """
        if (LOCAL_AI_BACKEND or "http").strip().lower() == "http":
            return

        # Guardrail: llama.cpp loads the model into the *current process*. In a multiprocess
        # worker (Celery prefork), this will duplicate the model per process and can OOM.
        concurrency, pool = local_ai_guardrail_inputs_from_env()
        guardrail_message = local_ai_runtime_guardrail_message(
            backend=LOCAL_AI_BACKEND,
            allow_multiprocess=LOCAL_AI_ALLOW_MULTIPROCESS,
            require_solo_pool=LOCAL_AI_REQUIRE_SOLO_POOL,
            concurrency=concurrency,
            pool=pool,
        )
        if guardrail_message:
            raise LocalAIConfigError(guardrail_message)

        if Llama is None:
            logger.error("Local AI model is unavailable (llama_cpp not installed). Falling back to heuristics.")
            return
        with self._lock:  # Acquire the lock (other threads will wait here)
            # Check if model is already loaded (another thread may have loaded it while we waited)
            if self.llm is not None:
                return  # Already loaded, nothing to do

            # Find where the model file is stored
            model_path = os.getenv("LOCAL_MODEL_PATH", "/models/gemma-3-270m-it-Q4_K_M.gguf")

            # Make sure the file actually exists
            if not os.path.exists(model_path):
                logger.warning(f"Model not found at {model_path}.")
                return  # Can't load what doesn't exist

            logger.info(f"Loading Local AI Model from {model_path}...")
            try:
                # Load the model (this is slow: ~5 seconds, ~500MB RAM)
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=LLM_CONTEXT_WINDOW,  # Maximum context size (how much text it can process at once)
                    n_gpu_layers=0,  # Don't use GPU (we want this to work on any machine)
                    verbose=False  # Don't print debug info
                )
                logger.info("AI Model loaded successfully.")
            except Exception as e:
                # AI model loading errors: Why keep this broad?
                # llama-cpp-python is an external C++ library that can raise many exception types:
                # - OSError: Model file not found or corrupted
                # - RuntimeError: CUDA/GPU errors, incompatible model format
                # - MemoryError: Model too large for available RAM
                # - ValueError: Invalid parameters (context size, layers)
                # - And potentially others from the underlying C++ code
                # DECISION: Keep broad exception handling here. It's safer to catch everything
                # than to miss a specific error type and crash the entire application.
                logger.error(f"Failed to load AI model: {e}")

    def summarize(self, text, doc_kind: str = "unknown"):
        """
        Generates a 3-bullet summary of meeting text using the local AI model.

        We truncate the input text to avoid exceeding the model's context window.
        """
        provider = self._get_provider()
        prompt = prepare_summary_prompt(text, doc_kind=doc_kind)
        raw = self._call_provider_text_or_none(
            lambda: (
                provider.summarize_text(
                    prompt,
                    max_tokens=LLM_SUMMARY_MAX_TOKENS,
                    temperature=0.1,
                )
                or ""
            ).strip(),
            operation_label="AI Summarization",
        )
        if not raw:
            return None
        normalized = _normalize_summary_output_to_bluf(raw, source_text=text)
        return normalized or raw

    def generate_json(self, prompt: str, max_tokens: int = 256) -> str | None:
        """
        Generate a JSON object from the local model.

        We attempt llama.cpp JSON-response enforcement first, then fall back to
        plain generation so callers can still apply strict post-parse validation.
        """
        provider = self._get_provider()
        text = self._call_provider_text_or_none(
            lambda: (provider.generate_json(prompt, max_tokens=max_tokens) or "").strip(),
            operation_label="AI JSON generation",
        )
        if not text:
            return None
        if text.startswith("{"):
            return text
        return "{" + text

    def summarize_agenda_items(
        self,
        meeting_title: str,
        meeting_date: str,
        items,
        truncation_meta: dict | None = None,
    ) -> str | None:
        """
        Generate a grounded decision-brief summary from structured agenda items.
        """
        provider = self._get_provider()

        try:
            return run_agenda_summary_pipeline(
                provider,
                meeting_title=meeting_title,
                meeting_date=meeting_date,
                items=items,
                truncation_meta=truncation_meta,
                helpers=_agenda_summary_helpers(),
            )
        except ProviderResponseError as e:
            logger.error(f"AI Agenda Items Summarization failed (response): {e}")
            logger.info("agenda_summary.counters agenda_summary_fallback_deterministic=%s", 1)
            return _deterministic_agenda_items_summary(
                items,
                max_bullets=AGENDA_SUMMARY_MAX_BULLETS,
                truncation_meta=truncation_meta,
            )
        except (ProviderTimeoutError, ProviderUnavailableError) as error:
            self._log_provider_failure("AI Agenda Items Summarization", error)
            return None
        except Exception as error:
            self._log_provider_failure("AI Agenda Items Summarization", error)
            return None

    def repair_title_spacing(self, raw_line: str) -> str | None:
        """
        Repair spacing/kerning artifacts in a single heading-like line.

        Contract:
        - spacing-only edits
        - no word substitutions
        - single-line plain-text output
        """
        provider = self._get_provider()
        source = (raw_line or "").strip()
        if not source:
            return None
        prompt = (
            "<start_of_turn>user\n"
            "Fix spacing/kerning errors in this ALL-CAPS meeting heading.\n"
            "Rules:\n"
            "- Do not change words.\n"
            "- Do not add or remove punctuation.\n"
            "- Only fix spaces between letters/words.\n"
            "- Output one plain-text line only.\n\n"
            f"Input: {source}\n"
            "<end_of_turn>\n"
            "<start_of_turn>model\n"
        )
        text = self._call_provider_text_or_none(
            lambda: (
                provider.summarize_text(
                    prompt,
                    max_tokens=64,
                    temperature=0.0,
                )
                or ""
            ).strip(),
            operation_label="AI title spacing repair",
        )
        if not text:
            return None
        return " ".join(text.splitlines()).strip()

    def extract_agenda(self, text):
        """
        Extracts individual agenda items from meeting text using the local AI model.

        Returns a list of agenda items with titles, page numbers, and descriptions.
        """
        provider = self._get_provider()
        mode = (AGENDA_SEGMENTATION_MODE or "balanced").strip().lower()
        raw_provider_content = None
        prompt = build_agenda_extraction_prompt(text, max_text=LLM_AGENDA_MAX_TEXT)
        try:
            raw_provider_content = (
                provider.extract_agenda(
                    prompt,
                    max_tokens=LLM_AGENDA_MAX_TOKENS,
                    temperature=0.1,
                )
                or ""
            ).strip()
        except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as error:
            logger.error("%s failed: %s", "AI Agenda Extraction", error)
        except Exception as error:
            # Provider/runtime extraction failures should preserve heuristic fallback behavior.
            logger.error("%s failed: %s", "AI Agenda Extraction", error)
        return run_agenda_extraction_pipeline(
            text=text,
            raw_provider_content=raw_provider_content,
            mode=mode,
            helpers=_agenda_extraction_helpers(),
        )
