import os
import json
import logging
import threading
import re
import multiprocessing
from rapidfuzz import fuzz
try:
    # Optional dependency: we still want the pipeline to run (heuristic fallbacks)
    # even if llama-cpp isn't installed in the current environment.
    from llama_cpp import Llama
except Exception:  # pragma: no cover
    Llama = None
from pipeline.utils import is_likely_human_name
from pipeline.config import (
    LLM_CONTEXT_WINDOW,
    LLM_SUMMARY_MAX_TEXT,
    LLM_SUMMARY_MAX_TOKENS,
    LLM_AGENDA_MAX_TEXT,
    LLM_AGENDA_MAX_TOKENS,
    AGENDA_FALLBACK_MAX_ITEMS_PER_DOC,
    AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH,
    AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE,
    AGENDA_SEGMENTATION_MODE,
    AGENDA_MIN_TITLE_CHARS,
    AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
    AGENDA_TOC_DEDUP_FUZZ,
    AGENDA_PROCEDURAL_REJECT_ENABLED,
    AGENDA_SUMMARY_PROFILE,
    AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS,
    AGENDA_SUMMARY_MAX_BULLETS,
    AGENDA_SUMMARY_SINGLE_ITEM_MODE,
    AGENDA_SUMMARY_TEMPERATURE,
    LOCAL_AI_ALLOW_MULTIPROCESS,
    LOCAL_AI_BACKEND,
)
from pipeline.summary_quality import is_summary_grounded, prune_unsupported_summary_lines
from pipeline.lexicon import (
    is_procedural_title as lexicon_is_procedural_title,
    is_contact_or_letterhead_noise as lexicon_is_contact_or_letterhead_noise,
    normalize_title_key as lexicon_normalize_title_key,
)
from pipeline.llm_provider import (
    InferenceProvider,
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

def _looks_like_multiprocess_worker() -> bool:
    """
    Best-effort detection of "this code is running inside a forked/child process".

    This is intentionally conservative: if we suspect multiprocess and the guardrail
    is enabled, we fail fast to avoid loading multiple GGUF model copies into RAM.
    """
    try:
        if multiprocessing.current_process().name != "MainProcess":
            return True
    except Exception:
        pass

    # Celery/worker env hints (best-effort; not authoritative).
    for key in ("CELERYD_CONCURRENCY", "WORKER_CONCURRENCY", "CELERY_WORKER_CONCURRENCY"):
        val = os.getenv(key)
        if val:
            try:
                if int(val) > 1:
                    return True
            except Exception:
                # Non-integer values are ignored; the process-name check is primary.
                pass
    return False

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
    kind = (doc_kind or "unknown").strip().lower()
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

def parse_llm_agenda_items(llm_text: str) -> list[dict]:
    """
    Parse the LLM's agenda extraction output.

    Why this exists:
    The model sometimes emits multi-line descriptions. A line-by-line parse will
    drop any continuation lines that don't match the header regex.

    We accept small formatting variance (dash/en-dash/em-dash/colon separators)
    and default missing/invalid page numbers to 1 rather than dropping the item.
    """
    text = (llm_text or "").strip()
    if not text:
        return []

    header = re.compile(r"(?im)^\s*ITEM\s+(?P<order>\d+)\s*:\s*")
    headers = list(header.finditer(text))
    if not headers:
        return []

    out: list[dict] = []
    for idx, m in enumerate(headers):
        try:
            order = int(m.group("order"))
        except Exception:
            continue

        start = m.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        if not body:
            continue

        # Prefer the explicit "(Page N)" marker when present.
        page_match = re.search(r"(?i)\(\s*page\s*(\d+)\s*\)", body)
        page = 1
        title_part = body
        desc_part = ""
        if page_match:
            try:
                page = int(page_match.group(1))
            except Exception:
                page = 1
            title_part = body[: page_match.start()].strip()
            desc_part = body[page_match.end() :].strip()
        else:
            # If the page marker is missing, split on the first reasonable separator.
            sep = re.search(r"\s+[-\u2013\u2014:]\s+", body)
            if sep:
                title_part = body[: sep.start()].strip()
                desc_part = body[sep.end() :].strip()
            else:
                # Fall back to first-line title + remainder as description.
                first, *rest = body.splitlines()
                title_part = first.strip()
                desc_part = " ".join([ln.strip() for ln in rest]).strip()

        title = " ".join((title_part or "").split())
        if not title:
            continue

        desc = (desc_part or "").strip()
        desc = re.sub(r"^[-\u2013\u2014:]\s*", "", desc)  # trim leading separator
        desc = " ".join(desc.split())

        out.append({"order": order, "title": title, "page_number": page, "description": desc})

    # If the model accidentally repeats ITEM numbers, keep the first occurrence.
    seen = set()
    deduped: list[dict] = []
    for item in out:
        key = (item["order"], item["title"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped

def iter_fallback_paragraphs(page_content: str) -> list[str]:
    """
    Extract paragraph-like chunks from a page for the weakest heuristic fallback.

    OCR often collapses paragraphs to single newlines. We prefer blank-line splits,
    but if blank lines are scarce we use "boundary lines" (numbered items, Subject:,
    and obvious headings) as delimiters.
    """
    raw = (page_content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return []

    blank_paras = [p.strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]
    if len(blank_paras) >= 3:
        return blank_paras

    boundary = re.compile(
        r"(?i)^\s*("
        r"subject\s*:"
        r"|item\s*#?\s*\d{1,3}\b"
        r"|#?\s*\d{1,2}(?:\.\d+)?[\.\):]\s+"
        r"|[A-Z][A-Z\s]{12,}"
        r")"
    )
    lines = [ln.strip() for ln in raw.splitlines()]
    paras: list[str] = []
    current: list[str] = []
    for ln in lines:
        if not ln:
            if current:
                paras.append("\n".join(current).strip())
                current = []
            continue
        if boundary.match(ln) and current:
            paras.append("\n".join(current).strip())
            current = [ln]
            continue
        current.append(ln)
    if current:
        paras.append("\n".join(current).strip())
    return [p for p in paras if p]


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
        backend = (LOCAL_AI_BACKEND or "inprocess").strip().lower()
        if backend not in {"inprocess", "http"}:
            backend = "inprocess"
        # Why this branch exists: backend mode is env-driven and can change between test runs.
        if self._provider is None or self._provider_backend != backend:
            if backend == "http":
                self._provider = HttpInferenceProvider()
            else:
                self._provider = InProcessLlamaProvider(self)
            self._provider_backend = backend
        return self._provider

    def _load_model(self):
        """
        Loads the AI model from disk into memory.

        This is wrapped in a lock because:
        1. Loading takes several seconds
        2. If two threads try to load simultaneously, we'd waste RAM and cause errors
        3. The lock ensures only ONE thread loads the model, others wait
        """
        if (LOCAL_AI_BACKEND or "inprocess").strip().lower() == "http":
            return

        # Guardrail: llama.cpp loads the model into the *current process*. In a multiprocess
        # worker (Celery prefork), this will duplicate the model per process and can OOM.
        if not LOCAL_AI_ALLOW_MULTIPROCESS and _looks_like_multiprocess_worker():
            raise LocalAIConfigError(
                "Unsafe LocalAI configuration detected (multiprocess worker). "
                "Run Celery with --concurrency=1 --pool=solo, or switch to a dedicated inference server backend."
            )

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

        try:
            raw = (
                provider.summarize_text(
                    prompt,
                    max_tokens=LLM_SUMMARY_MAX_TOKENS,
                    temperature=0.1,
                )
                or ""
            ).strip()
            if not raw:
                return None
            normalized = _normalize_summary_output_to_bluf(raw, source_text=text)
            return normalized or raw
        except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as e:
            logger.error(f"AI Summarization failed: {e}")
            return None
        except Exception as e:
            logger.error(f"AI Summarization failed: {e}")
            return None

    def generate_json(self, prompt: str, max_tokens: int = 256) -> str | None:
        """
        Generate a JSON object from the local model.

        We attempt llama.cpp JSON-response enforcement first, then fall back to
        plain generation so callers can still apply strict post-parse validation.
        """
        provider = self._get_provider()
        try:
            if hasattr(provider, "generate_json"):
                text = (provider.generate_json(prompt, max_tokens=max_tokens) or "").strip()
            else:
                text = (
                    provider.summarize_text(
                        prompt,
                        max_tokens=max_tokens,
                        temperature=0.0,
                    )
                    or ""
                ).strip()
            if not text:
                return None
            if text.startswith("{"):
                return text
            return "{" + text
        except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as e:
            logger.error(f"AI JSON generation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"AI JSON generation failed: {e}")
            return None

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

        structured_items = [_coerce_agenda_summary_item(item, idx=i) for i, item in enumerate(items or [])]
        filtered_items = []
        summary_filtered_notice_fragments = 0
        for item in structured_items:
            serialized = item.get("title", "")
            if item.get("description"):
                serialized = f"{serialized} - {item['description']}"
            if _should_drop_from_agenda_summary(serialized):
                summary_filtered_notice_fragments += 1
                continue
            filtered_items.append(item)

        counters = {
            "agenda_summary_items_total": len(structured_items),
            "agenda_summary_items_included": len(filtered_items),
            "agenda_summary_items_truncated": int((truncation_meta or {}).get("items_truncated", 0)),
            "agenda_summary_input_chars": int((truncation_meta or {}).get("input_chars", 0)),
            "agenda_summary_single_item_mode": 0,
            "agenda_summary_unknowns_count": 0,
            "agenda_summary_grounding_pruned_lines": 0,
            "agenda_summary_fallback_deterministic": 0,
        }

        scaffold = _build_agenda_summary_scaffold(
            filtered_items,
            truncation_meta=truncation_meta,
            profile=AGENDA_SUMMARY_PROFILE,
        )
        counters["agenda_summary_single_item_mode"] = int(bool(scaffold.get("single_item_mode")))
        counters["agenda_summary_unknowns_count"] = len(scaffold.get("unknowns", []))

        logger.info(
            "agenda_summary.counters total_items=%s kept_items=%s summary_filtered_notice_fragments=%s "
            "agenda_summary_items_total=%s agenda_summary_items_included=%s agenda_summary_items_truncated=%s "
            "agenda_summary_input_chars=%s agenda_summary_single_item_mode=%s agenda_summary_unknowns_count=%s",
            len(structured_items),
            len(filtered_items),
            summary_filtered_notice_fragments,
            counters["agenda_summary_items_total"],
            counters["agenda_summary_items_included"],
            counters["agenda_summary_items_truncated"],
            counters["agenda_summary_input_chars"],
            counters["agenda_summary_single_item_mode"],
            counters["agenda_summary_unknowns_count"],
        )

        if not filtered_items:
            counters["agenda_summary_fallback_deterministic"] = 1
            logger.info("agenda_summary.counters agenda_summary_fallback_deterministic=%s", 1)
            return _deterministic_agenda_items_summary([], truncation_meta=truncation_meta)

        prompt = _prepare_structured_agenda_items_summary_prompt(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            items=filtered_items,
            scaffold=scaffold,
            truncation_meta=truncation_meta,
        )
        grounding_source = _agenda_items_source_text(filtered_items)

        try:
            raw = (
                provider.summarize_agenda_items(
                    prompt,
                    max_tokens=LLM_SUMMARY_MAX_TOKENS,
                    temperature=AGENDA_SUMMARY_TEMPERATURE,
                )
                or ""
            ).strip()
            cleaned = _strip_markdown_emphasis(raw).strip()
            cleaned = _strip_llm_acknowledgements(cleaned).strip()
            cleaned = _normalize_bullets_to_dash(cleaned).strip()
            if cleaned and not cleaned.startswith("BLUF:"):
                cleaned = f"BLUF: {scaffold.get('bluf_seed', 'Agenda summary.')}"
            cleaned = _ensure_single_item_decision_section(cleaned, scaffold)

            pruned, removed_count = prune_unsupported_summary_lines(cleaned, grounding_source)
            counters["agenda_summary_grounding_pruned_lines"] = int(removed_count)
            if removed_count:
                logger.info(
                    "agenda_summary.counters agenda_summary_grounding_pruned_lines=%s",
                    removed_count,
                )
            cleaned = pruned or cleaned

            grounded = is_summary_grounded(cleaned, grounding_source)
            if (not grounded.is_grounded) or _agenda_items_summary_is_too_short(cleaned):
                counters["agenda_summary_fallback_deterministic"] = 1
                logger.info("agenda_summary.counters agenda_summary_fallback_deterministic=%s", 1)
                return _deterministic_agenda_items_summary(
                    filtered_items,
                    max_bullets=AGENDA_SUMMARY_MAX_BULLETS,
                    truncation_meta=truncation_meta,
                )
            return cleaned
        except ProviderResponseError as e:
            logger.error(f"AI Agenda Items Summarization failed (response): {e}")
            counters["agenda_summary_fallback_deterministic"] = 1
            logger.info("agenda_summary.counters agenda_summary_fallback_deterministic=%s", 1)
            return _deterministic_agenda_items_summary(
                filtered_items,
                max_bullets=AGENDA_SUMMARY_MAX_BULLETS,
                truncation_meta=truncation_meta,
            )
        except (ProviderTimeoutError, ProviderUnavailableError) as e:
            logger.error(f"AI Agenda Items Summarization failed: {e}")
            return None
        except Exception as e:
            logger.error(f"AI Agenda Items Summarization failed: {e}")
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
        try:
            text = (
                provider.summarize_text(
                    prompt,
                    max_tokens=64,
                    temperature=0.0,
                )
                or ""
            ).strip()
            return " ".join(text.splitlines()).strip()
        except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as e:
            logger.error(f"AI title spacing repair failed: {e}")
            return None
        except Exception as e:
            logger.error(f"AI title spacing repair failed: {e}")
            return None

    def extract_agenda(self, text):
        """
        Extracts individual agenda items from meeting text using the local AI model.

        Returns a list of agenda items with titles, page numbers, and descriptions.
        """
        provider = self._get_provider()

        items = []
        mode = (AGENDA_SEGMENTATION_MODE or "balanced").strip().lower()
        stats = {
            "rejected_procedural": 0,
            "rejected_contact": 0,
            "rejected_low_substance": 0,
            "rejected_lowercase_fragment": 0,
            "rejected_notice_fragment": 0,
            "rejected_tabular_fragment": 0,
            "rejected_nested_subitem": 0,
            "context_carryover_pages": 0,
            "stop_marker_candidates": 0,
            "stopped_after_end_marker": 0,
            "rejected_noise": 0,
            "deduped_toc_duplicates": 0,
            "accepted_items_final": 0,
        }
        parse_state = {
            "active_parent_item": None,
            "active_parent_page": None,
            "parent_context_confidence": 0.0,
            "seen_top_level_items": 0,
        }

        def normalize_spaces(value):
            return _normalize_spaces(value)

        def looks_like_spaced_ocr(value):
            tokens = [t for t in normalize_spaces(value).split(" ") if t]
            if not tokens:
                return False
            single_char_tokens = sum(1 for t in tokens if len(t) == 1 and t.isalpha())
            return (single_char_tokens / len(tokens)) >= 0.6

        def is_noise_title(title):
            lowered = normalize_spaces(title).lower()
            if not lowered:
                return True
            if len(lowered) < AGENDA_MIN_TITLE_CHARS:
                return True
            if _is_procedural_noise_title(lowered):
                return True
            if _is_contact_or_letterhead_noise(lowered, ""):
                return True
            # IP / endpoint fragments from teleconference templates should not become agenda items.
            if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", lowered):
                return True
            if _looks_like_teleconference_endpoint_line(lowered):
                return True
            if re.search(r"\b(us west|us east)\b", lowered):
                return True
            if looks_like_spaced_ocr(lowered):
                return True
            if lowered.startswith("http://") or lowered.startswith("https://"):
                return True
            # URLs embedded in a line are almost always boilerplate, not an agenda topic.
            if "http://" in lowered or "https://" in lowered or "www." in lowered:
                return True
            # Dates, times, and location/address lines are metadata, not agenda topics.
            if re.match(r"^[A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}$", title):
                return True
            if re.search(r"\b\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|am|pm)\b", lowered):
                return True
            if re.search(r"\b\d{2,6}\s+[A-Za-z].*(street|st|avenue|ave|road|rd|blvd|boulevard)\b", lowered):
                return True
            if "mayor" in lowered or "councilmembers" in lowered:
                return True
            # Participation/COVID/ADA boilerplate often looks like a "numbered item".
            # This keeps it out of structured agenda output.
            if _looks_like_agenda_segmentation_boilerplate(lowered):
                return True
            # Common accessibility / participation boilerplate.
            if re.search(r"\b(disability[- ]related|accommodation\\(s\\)|auxiliary aids|interpreters?)\b", lowered):
                return True
            if re.search(r"\b(brown act|executive orders?)\b", lowered):
                return True
            if re.search(r"\b(communication access information|questions regarding|public comment portion)\b", lowered):
                return True
            if re.search(r"\b(agendas? and agenda reports?|agenda reports? may be accessed)\b", lowered):
                return True
            if re.search(r"\b(may participate in the public comment|meeting will be conducted in accordance)\b", lowered):
                return True
            if re.search(r"\b(city clerk|cityofberkeley\\.info|cityofberkeley\\.org)\b", lowered):
                return True
            if "as follows" in lowered and len(lowered) <= 40:
                return True
            if lowered.endswith(":") and len(lowered) <= 45:
                return True

            # Common meeting header noise that should not become agenda items.
            header_noise = [
                "special closed meeting",
                "calling a special meeting",
                "agenda packet",
                "table of contents",
                "supplemental communications",
                "form letters",
            ]
            if any(token in lowered for token in header_noise):
                return True
            # Narrow legal-notice boilerplate pattern (Berkeley Levine Act block).
            if "government code section 84308" in lowered or "levine act" in lowered:
                return True
            if "parties to a proceeding involving a license, permit, or other" in lowered:
                return True
            if re.match(r"^district\s+\d+\b", lowered):
                return True

            return False

        def add_item(order, title, page_number, description, result="", source_type="fallback", context=None):
            clean_title = normalize_spaces(title)
            clean_description = normalize_spaces(description) if description else ""
            if source_type == "fallback" and _is_probable_line_fragment_title(clean_title):
                stats["rejected_lowercase_fragment"] += 1
                return
            if _is_tabular_fragment(clean_title, clean_description, context=context):
                stats["rejected_tabular_fragment"] += 1
                return
            if _looks_like_agenda_segmentation_boilerplate(clean_title):
                stats["rejected_notice_fragment"] += 1
                return
            if is_noise_title(clean_title):
                stats["rejected_noise"] += 1
                return

            if source_type == "llm":
                if _is_procedural_noise_title(clean_title):
                    stats["rejected_procedural"] += 1
                    return
                if _is_contact_or_letterhead_noise(clean_title, clean_description):
                    stats["rejected_contact"] += 1
                    return
                if not _should_accept_llm_item(
                    {
                        "title": clean_title,
                        "description": clean_description,
                        "page_number": page_number,
                        "context": context or {},
                    },
                    mode=mode,
                ):
                    stats["rejected_low_substance"] += 1
                    return

            items.append({
                "order": order,
                "title": clean_title,
                "page_number": page_number,
                "description": clean_description,
                "classification": "Agenda Item",
                "result": normalize_spaces(result)
            })

        def is_probable_person_name(value):
            """
            Heuristic guardrail:
            speaker roll lists are often numbered lines with person names.
            """
            clean = normalize_spaces(value)
            if not clean:
                return False
            clean = re.sub(r"\(\d+\)", "", clean).strip()
            lowered = clean.lower()
            # Speaker roll entries frequently contain this phrase.
            if "on behalf of" in lowered:
                return True
            if re.search(
                r"\b(update|plan|zoning|hearing|budget|report|session|meeting|ordinance|resolution|project|communications|adjournment|amendment|specific|corridor|worksession)\b",
                lowered
            ):
                return False
            if is_likely_human_name(clean, allow_single_word=True):
                return True
            # Catch multi-person entries that may include "&" / "and".
            if " and " in lowered or " & " in clean:
                tokens = re.split(r"\s+(?:and|&)\s+|\s+", clean)
                tokens = [t for t in tokens if t]
                if 2 <= len(tokens) <= 8 and all(re.match(r"^[A-Z][A-Za-z'’\.\-]*$", t) for t in tokens):
                    return True
            return False

        def _merge_wrapped_title_lines(base_title: str, block_text: str) -> str:
            """
            Merge wrapped title continuation lines for fallback parsing.

            Some PDFs split a single long agenda title across multiple lines. We collect
            immediate continuation lines until we hit known section boundaries.
            """
            title = normalize_spaces(base_title)
            if not block_text:
                return title

            boundary_re = re.compile(
                r"(?i)^\s*(from|recommendation|recommended action|financial implications|contact|vote|result|action|subject)\s*:"
            )
            # Stop if we hit a new numbered/lettered list entry.
            list_item_re = re.compile(r"^\s*(?:item\s*)?#?\s*(\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+")

            added = 0
            for raw_line in (block_text or "").splitlines():
                line = raw_line.strip()
                if not line:
                    if added > 0:
                        break
                    continue
                if boundary_re.match(line) or list_item_re.match(line):
                    break
                if len(line) < 3:
                    break
                title = normalize_spaces(f"{title} {line}")
                added += 1
                # Keep title stitching conservative.
                if added >= 2:
                    break
            return title

        def split_text_by_page_markers(raw_text):
            """
            Build page chunks from either explicit OCR tags ([PAGE N]) or document headers
            like "... Page 2". This avoids defaulting everything to page 1 when OCR tags are sparse.
            """
            markers = []
            for match in re.finditer(r"\[PAGE\s+(\d+)\]", raw_text, flags=re.IGNORECASE):
                markers.append((match.start(), int(match.group(1))))
            for match in re.finditer(r"(?im)^.*\bPage\s+(\d+)\s*$", raw_text):
                markers.append((match.start(), int(match.group(1))))

            if not markers:
                return [(1, raw_text)]

            markers.sort(key=lambda item: item[0])

            # Deduplicate near-identical markers that point to same page.
            deduped = []
            for pos, page in markers:
                if deduped and deduped[-1][1] == page and (pos - deduped[-1][0]) < 120:
                    continue
                deduped.append((pos, page))

            chunks = []
            for i, (start_pos, page_num) in enumerate(deduped):
                end_pos = deduped[i + 1][0] if i + 1 < len(deduped) else len(raw_text)
                chunk = raw_text[start_pos:end_pos].strip()
                if chunk:
                    chunks.append((page_num, chunk))
            return chunks or [(1, raw_text)]

        if provider is not None:
            # We increase context slightly to catch more items, focusing on the start
            safe_text = text[:LLM_AGENDA_MAX_TEXT]
            
            # PROMPT: We now ask for Page numbers and a clean list.
            # We explicitly tell it to ignore boilerplate and headers.
            prompt = (
                "<start_of_turn>user\n"
                "Extract ONLY the real agenda items from this meeting document. "
                "Include the page number where each item starts. "
                "Format: ITEM [Order]: [Title] (Page [X]) - [Brief Summary]\n"
                "Rules:\n"
                "- Do NOT extract procedural placeholders (Call to Order, Roll Call, Adjournment, Public Comment).\n"
                "- Do NOT extract teleconference/Zoom/ADA/how-to-attend instructions.\n"
                "- Do NOT extract Table of Contents entries.\n"
                "- Do NOT extract contact/letterhead metadata (addresses, phone/fax, email, website, From:/To: lines).\n\n"
                "- HIERARCHY RULE: If a primary item contains a table/list/subparts, extract ONLY the parent item. "
                "Do not emit each row/sub-part as a separate item.\n\n"
                f"Text:\n{safe_text}<end_of_turn>\n"
                "<start_of_turn>model\n"
                "ITEM 1:"
            )
            
            try:
                raw_content = (
                    provider.extract_agenda(
                        prompt,
                        max_tokens=LLM_AGENDA_MAX_TOKENS,
                        temperature=0.1,
                    )
                    or ""
                ).strip()
                # The prompt pins the model's output stream at "ITEM 1:", but llama.cpp
                # returns only the continuation text. Only reconstruct "ITEM 1:" when the
                # continuation looks like it actually followed the requested format.
                content = raw_content
                if (
                    "(page" in raw_content.lower()
                    or re.search(r"(?im)^\s*ITEM\s+\d+\s*:", raw_content)
                    or re.search(r"(?im)\n\s*ITEM\s+\d+\s*:", raw_content)
                ):
                    content = "ITEM 1:" + raw_content

                # Parse across the full model output so we don't drop multi-line descriptions.
                for parsed in parse_llm_agenda_items(content):
                    add_item(
                        parsed["order"],
                        parsed["title"],
                        parsed["page_number"],
                        parsed["description"],
                        source_type="llm",
                        context={"has_active_parent": False},
                    )
            except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as e:
                logger.error(f"AI Agenda Extraction failed: {e}")
            except Exception as e:
                # AI agenda extraction errors: Same rationale as above
                # The model can fail during generation, response parsing, or regex matching
                # DECISION: Log the error but return partial results (items extracted so far)
                # rather than crashing. The fallback heuristic will catch items anyway.
                logger.error(f"AI Agenda Extraction failed: {e}")

        # FALLBACK: If AI fails, use text heuristics with page-aware chunking.
        if not items:
            page_chunks = split_text_by_page_markers(text)
            for page_idx, (page_num, page_content) in enumerate(page_chunks):
                if parse_state["active_parent_item"] is not None and page_idx > 0:
                    previous_page_num = page_chunks[page_idx - 1][0]
                    if previous_page_num != page_num:
                        stats["context_carryover_pages"] += 1

                trailing_text = "\n".join(chunk for _, chunk in page_chunks[page_idx:])
                truncated_page_content = page_content
                stop_after_page = False
                lines = page_content.splitlines(keepends=True)
                cursor = 0
                for line_idx, raw_line in enumerate(lines):
                    candidate_line = raw_line.strip()
                    line_len = len(raw_line)
                    if not _looks_like_end_marker_line(candidate_line):
                        cursor += line_len
                        continue
                    stats["stop_marker_candidates"] += 1
                    lookahead_window = "".join(lines[line_idx : line_idx + 25]) + "\n" + trailing_text[:2500]
                    if _should_stop_after_marker(candidate_line, lookahead_window):
                        truncated_page_content = page_content[:cursor]
                        stats["stopped_after_end_marker"] += 1
                        stop_after_page = True
                        break
                    cursor += line_len

                page_content = truncated_page_content
                page_lower = page_content.lower()
                speaker_context = (
                    "communications" in page_lower
                    or "speakers" in page_lower
                    or "public comment" in page_lower
                    or "item #1" in page_lower
                    or "item #2" in page_lower
                )

                # Prefer explicit numbered agenda lines when available.
                numbered_line_pattern = re.compile(
                    r"(?m)^\s*(?:item\s*)?#?\s*(\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+(.{6,400})$"
                )

                numbered_lines = list(numbered_line_pattern.finditer(page_content))
                if numbered_lines:
                    # If a numbered block is mostly person-name lines, it is likely a speaker list.
                    person_like_count = sum(
                        1 for m in numbered_lines if is_probable_person_name(m.group(2).strip())
                    )
                    person_heavy_numbered_list = (
                        len(numbered_lines) >= 5
                        and (person_like_count / len(numbered_lines)) >= 0.5
                    )

                    # If a numbered block is mostly participation/COVID/ADA boilerplate,
                    # treat it as a template section and do not convert it into items.
                    noise_like_count = sum(
                        1 for m in numbered_lines
                        if is_noise_title(m.group(2).strip())
                        or _looks_like_agenda_segmentation_boilerplate(m.group(2).strip())
                    )
                    mostly_noise_numbered_list = (
                        len(numbered_lines) >= 4
                        and (noise_like_count / len(numbered_lines)) >= 0.5
                    )
                    if mostly_noise_numbered_list:
                        logger.debug(
                            "agenda_segmentation.skip_numbered_block",
                            extra={
                                "page": page_num,
                                "numbered_lines": len(numbered_lines),
                                "noise_like": noise_like_count,
                            },
                        )
                        # Fall through to paragraph parsing for this page (and later pages).
                        numbered_lines = []

                    for idx, match in enumerate(numbered_lines):
                        marker = match.group(1)
                        title = match.group(2).strip()
                        marker_normalized = (marker or "").strip()
                        marker_upper = marker_normalized.upper()
                        is_top_level_numeric = bool(re.fullmatch(r"\d{1,2}(?:\.\d+)?", marker_normalized))
                        preceding_window = page_content[max(0, match.start() - 500):match.start()].lower()
                        looks_like_nested_numeric_recommendation = bool(
                            parse_state["active_parent_item"]
                            and is_top_level_numeric
                            and "recommendation:" in preceding_window
                            and ("would:" in preceding_window or "following action" in preceding_window)
                            and "subject:" not in preceding_window[-160:]
                        )
                        is_contextual_subitem = bool(
                            parse_state["active_parent_item"]
                            and (
                                re.fullmatch(r"[A-Z]", marker_upper)
                                or re.fullmatch(r"[IVXLC]+", marker_upper)
                                or re.fullmatch(r"\d{1,2}[A-Za-z]", marker_normalized)
                                or looks_like_nested_numeric_recommendation
                            )
                        )
                        if is_contextual_subitem:
                            stats["rejected_nested_subitem"] += 1
                            continue
                        if is_probable_person_name(title) and (
                            speaker_context or person_heavy_numbered_list
                        ):
                            # Do not promote speaker-name roll calls into agenda topics.
                            continue
                        if _is_procedural_noise_title(title):
                            continue
                        if _is_contact_or_letterhead_noise(title, ""):
                            continue

                        block_start = match.end()
                        block_end = numbered_lines[idx + 1].start() if idx + 1 < len(numbered_lines) else len(page_content)
                        block_text = page_content[block_start:block_end]
                        title = _merge_wrapped_title_lines(title, block_text)
                        vote_match = re.search(r"(?im)\bVote:\s*([^\n\r]+)", block_text)
                        vote_result = vote_match.group(1) if vote_match else ""

                        before_count = len(items)
                        add_item(
                            len(items) + 1,
                            title,
                            page_num,
                            f"Agenda section {marker}",
                            result=vote_result,
                            context={
                                "has_active_parent": parse_state["active_parent_item"] is not None,
                                "parent_context_confidence": parse_state["parent_context_confidence"],
                                "seen_top_level_items": parse_state["seen_top_level_items"],
                            },
                        )
                        if len(items) > before_count and is_top_level_numeric:
                            parse_state["active_parent_item"] = normalize_spaces(title)
                            parse_state["active_parent_page"] = page_num
                            parse_state["parent_context_confidence"] = 1.0
                            parse_state["seen_top_level_items"] += 1
                        if len(items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC:
                            break
                    if numbered_lines:
                        if stop_after_page:
                            break
                        continue

                # Fallback for unnumbered formats: use paragraph starts carefully.
                paragraphs = [
                    p for p in iter_fallback_paragraphs(page_content)
                    if 10 < len(p.strip()) < 1000
                ]

                added_from_paragraphs = 0
                consecutive_rejects = 0
                for p in paragraphs:
                    if len(items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC:
                        break
                    if added_from_paragraphs >= AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH:
                        break

                    lines = p.split("\n")
                    if not lines:
                        consecutive_rejects += 1
                        if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                            break
                        continue

                    title = re.sub(r"^\s*\d+(?:\.\d+)?[\.\):]?\s*", "", lines[0].strip())
                    title_l = title.lower()

                    # Keep only plausible title lengths and skip common extraction junk.
                    if not (10 < len(title) < 150):
                        consecutive_rejects += 1
                        if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                            break
                        continue

                    if any(b in title_l for b in ["page", "packet", "continuing"]):
                        consecutive_rejects += 1
                        if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                            break
                        continue

                    if title_l.startswith("item #") or is_probable_person_name(title):
                        consecutive_rejects += 1
                        if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                            break
                        continue

                    desc = (p[:500] + "...") if len(p) > 500 else p
                    before = len(items)
                    add_item(
                        len(items) + 1,
                        title,
                        page_num,
                        desc,
                        context={
                            "has_active_parent": parse_state["active_parent_item"] is not None,
                            "parent_context_confidence": parse_state["parent_context_confidence"],
                            "seen_top_level_items": parse_state["seen_top_level_items"],
                        },
                    )
                    if len(items) > before:
                        added_from_paragraphs += 1
                        consecutive_rejects = 0
                    else:
                        consecutive_rejects += 1
                        if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                            break

                if len(items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC:
                    break
                if stop_after_page:
                    break

        items, deduped = _dedupe_agenda_items_for_document(items)
        stats["deduped_toc_duplicates"] = deduped
        stats["accepted_items_final"] = len(items)
        logger.info(
            "agenda_segmentation.counters mode=%s accepted_items_final=%s rejected_procedural=%s rejected_contact=%s rejected_low_substance=%s rejected_lowercase_fragment=%s rejected_notice_fragment=%s rejected_tabular_fragment=%s rejected_nested_subitem=%s context_carryover_pages=%s stop_marker_candidates=%s stopped_after_end_marker=%s rejected_noise=%s deduped_toc_duplicates=%s",
            mode,
            stats["accepted_items_final"],
            stats["rejected_procedural"],
            stats["rejected_contact"],
            stats["rejected_low_substance"],
            stats["rejected_lowercase_fragment"],
            stats["rejected_notice_fragment"],
            stats["rejected_tabular_fragment"],
            stats["rejected_nested_subitem"],
            stats["context_carryover_pages"],
            stats["stop_marker_candidates"],
            stats["stopped_after_end_marker"],
            stats["rejected_noise"],
            stats["deduped_toc_duplicates"],
        )
        return items
