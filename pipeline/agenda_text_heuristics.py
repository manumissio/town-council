import re

from rapidfuzz import fuzz

from pipeline.config import (
    AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
    AGENDA_MIN_TITLE_CHARS,
    AGENDA_PROCEDURAL_REJECT_ENABLED,
    AGENDA_TOC_DEDUP_FUZZ,
)
from pipeline.lexicon import (
    is_contact_or_letterhead_noise as lexicon_is_contact_or_letterhead_noise,
    is_procedural_title as lexicon_is_procedural_title,
    normalize_title_key as lexicon_normalize_title_key,
)


def dedupe_lines_preserve_order(lines):
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


def normalize_spaces(value: str) -> str:
    if value is None:
        raw = ""
    elif isinstance(value, str):
        raw = value
    else:
        # Some tests use MagicMock placeholders for optional fields.
        raw = str(value)
    return re.sub(r"\s+", " ", raw).strip()


def normalized_title_key(value: str) -> str:
    # Single lexicon source keeps normalization consistent across pipeline/API.
    return lexicon_normalize_title_key(normalize_spaces(value))


def first_alpha_char(value: str) -> str | None:
    """
    Return the first alphabetical character in a string, or None when absent.
    """
    match = re.search(r"[a-zA-Z]", value or "")
    return match.group(0) if match else None


def is_probable_line_fragment_title(title: str) -> bool:
    """
    Detect line-fragment titles from pleading-paper numbering/OCR artifacts.

    Why this is fallback-scoped:
    Heuristic fallback parsing sees raw lines like "16 in the appropriate ...".
    We only apply this trap there, not to direct LLM-parsed items.
    """
    normalized = normalize_spaces(title)
    if not normalized:
        return True

    alpha_char = first_alpha_char(normalized)
    if not alpha_char:
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

    return alpha_char.islower()


def is_procedural_noise_title(title: str) -> bool:
    """
    Return True for procedural placeholders that should not be treated as legislative items.

    Important: keep this precise. Broad substring matching (for example "approval")
    causes silent drops of substantive titles such as "Approval of Contract ...".
    """
    return lexicon_is_procedural_title(title, reject_enabled=AGENDA_PROCEDURAL_REJECT_ENABLED)


def is_contact_or_letterhead_noise(title: str, desc: str = "") -> bool:
    """
    Return True for contact/letterhead metadata commonly mis-read as agenda items.
    """
    return lexicon_is_contact_or_letterhead_noise(normalize_spaces(title), normalize_spaces(desc))


def llm_item_substance_score(title: str, desc: str = "") -> float:
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

    legislative_terms = (
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
    if any(term in lowered for term in legislative_terms):
        score += 0.35

    action_terms = ("approve", "adopt", "authorize", "consider", "review", "receive", "vote")
    if any(term in lowered for term in action_terms):
        score += 0.15

    if len(desc_norm) >= AGENDA_MIN_SUBSTANTIVE_DESC_CHARS:
        score += 0.20

    return max(0.0, min(1.0, score))


def looks_like_attendance_boilerplate(line: str) -> bool:
    """
    Return True when a line is probably attendance/public-comment/ADA boilerplate.
    """
    if not line:
        return False

    lowered = line.strip().lower()

    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", lowered):
        return True
    if re.search(r"\b\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}\b", lowered):
        return True
    if re.search(r"\bmeeting id\b|\bwebinar id\b|\bpasscode\b", lowered):
        return True

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
    return any(fragment in lowered for fragment in boilerplate_fragments)


def looks_like_teleconference_endpoint_line(line: str) -> bool:
    """
    Return True for short endpoint-list lines that show up in teleconference instructions.
    """
    if not line:
        return False

    lowered = (line or "").strip().lower()
    match = re.match(r"^\s*(\d{2,3})\.(\d{2,3})(?:\.(\d{1,3}))?(?:\.(\d{1,3}))?\s*(.*)$", lowered)
    if not match:
        return False

    first_number = int(match.group(1))
    second_number = int(match.group(2))
    if first_number < 20 or second_number < 20:
        return False

    tail = (match.group(5) or "").strip()
    if not tail:
        return True
    return tail.startswith("(")


def looks_like_agenda_segmentation_boilerplate(line: str) -> bool:
    """
    Return True when a line is probably boilerplate that should not become an agenda item.
    """
    if not line:
        return False

    lowered = (line or "").strip().lower()
    compact = re.sub(r"[^a-z0-9]+", "", lowered)

    if looks_like_attendance_boilerplate(lowered):
        return True

    grouped_fragments = (
        (
            "covid",
            "covid-19",
            "coronavirus",
            "state of emergency",
            "executive order",
            "governor newsom",
            "order no-",
            "order no.",
        ),
        (
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
        ),
        (
            "communication access",
            "disability",
            "accommodation",
            "auxiliary aids",
            "interpreters",
            "americans with disabilities act",
            "ada",
        ),
        (
            "public advisory",
            "live captioned",
            "captioned broadcast",
            "captioned broadcasts",
            "broadcasts of council meetings",
            "council meetings are available",
            "b-tv",
            "channel 33",
            "kpfa",
            "kpbf",
            "radio 89.3",
            "internet video stream",
            "video stream",
            "webcast",
            "livestream",
            "live stream",
        ),
        (
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
        ),
        (
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
        ),
        (
            "annotated agenda",
            "special meeting of the",
            "calling a special meeting",
            "proclamation",
            "planning commission agenda",
        ),
        (
            "mentimeter",
            "slido",
            "poll",
            "survey",
            "enter code",
            "mobile device",
            "qr code",
        ),
    )
    for fragments in grouped_fragments:
        if any(fragment in lowered for fragment in fragments):
            return True
        compact_fragments = tuple(re.sub(r"[^a-z0-9]+", "", fragment) for fragment in fragments)
        if any(fragment and fragment in compact for fragment in compact_fragments):
            return True

    if "email address" in lowered:
        return True
    if "will not be disclosed" in lowered:
        return True
    if "connect to the meeting" in lowered:
        return True
    if "you may enter" in lowered and ("designation" in lowered or "resident" in lowered):
        return True
    if looks_like_teleconference_endpoint_line(lowered):
        return True
    return False


def looks_like_sub_marker_title(value: str) -> bool:
    """
    Detect likely nested list markers (A., 1a., i.) that often represent child rows.
    """
    title = normalize_spaces(value)
    return bool(re.match(r"^(?:[A-Z]\.|[0-9]{1,2}[a-z]\.|[ivxlcdm]+\.)\s+", title, flags=re.IGNORECASE))


def is_tabular_fragment(title: str, desc: str = "", context: dict | None = None) -> bool:
    """
    Detect flattened table/list rows that should not be promoted to top-level agenda items.
    """
    raw_title = title or ""
    raw_desc = desc or ""
    raw_combined = f"{raw_title} {raw_desc}".strip()
    combined = normalize_spaces(raw_combined)
    if not combined or len(combined) > 180:
        return False

    total_chars = len(combined)
    alpha_chars = sum(1 for char in combined if char.isalpha())
    alpha_density = (alpha_chars / total_chars) if total_chars else 1.0

    tokens = [token for token in re.split(r"\s+", combined.lower()) if token]
    number_symbol_ratio = 0.0
    if tokens:
        number_symbol_tokens = sum(1 for token in tokens if re.search(r"[0-9$%/|#]", token))
        number_symbol_ratio = number_symbol_tokens / len(tokens)

    strong_primary = len(combined) <= 150 and alpha_density < 0.60 and number_symbol_ratio >= 0.25

    secondary_signals = 0
    if "\t" in raw_combined or re.search(r" {3,}", raw_combined):
        secondary_signals += 1

    has_active_parent = bool((context or {}).get("has_active_parent"))
    if has_active_parent and looks_like_sub_marker_title(raw_title):
        secondary_signals += 1

    if tokens:
        number_symbol_tokens = sum(1 for token in tokens if re.search(r"[0-9$%/|#]", token))
        if (number_symbol_tokens / len(tokens)) >= 0.35:
            secondary_signals += 1
        verb_like_tokens = (
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
        if len(tokens) >= 5 and not any(verb in " ".join(tokens) for verb in verb_like_tokens):
            secondary_signals += 1

    if strong_primary:
        return True
    if has_active_parent and secondary_signals >= 2:
        return True
    if secondary_signals >= 3 and len(combined) <= 120:
        return True
    return False


def should_accept_llm_item(item: dict, mode: str = "balanced") -> bool:
    """
    Acceptance gate for LLM-parsed items only.
    """
    title = normalize_spaces(item.get("title", ""))
    desc = normalize_spaces(item.get("description", ""))
    context = item.get("context") if isinstance(item, dict) else None
    if len(title) < AGENDA_MIN_TITLE_CHARS:
        return False
    if is_procedural_noise_title(title):
        return False
    if is_contact_or_letterhead_noise(title, desc):
        return False
    if is_tabular_fragment(title, desc, context=context):
        return False

    threshold_map = {"recall": 0.28, "balanced": 0.45, "aggressive": 0.58}
    threshold = threshold_map.get((mode or "balanced").lower(), threshold_map["balanced"])
    score = llm_item_substance_score(title, desc)

    if len(desc) < AGENDA_MIN_SUBSTANTIVE_DESC_CHARS and score < threshold:
        return False
    return score >= threshold


def dedupe_agenda_items_for_document(items: list[dict]) -> tuple[list[dict], int]:
    """
    Collapse near-duplicate agenda titles within one document.
    """
    if not items:
        return items, 0

    groups: list[list[tuple[int, dict]]] = []
    for idx, item in enumerate(items):
        title_key = normalized_title_key(item.get("title", ""))
        if not title_key:
            continue
        matched = None
        for group_idx, group in enumerate(groups):
            reference_key = normalized_title_key(group[0][1].get("title", ""))
            if fuzz.token_sort_ratio(title_key, reference_key) >= AGENDA_TOC_DEDUP_FUZZ:
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
        winner = max(
            group,
            key=lambda pair: (
                int(pair[1].get("page_number") or 0),
                llm_item_substance_score(pair[1].get("title", ""), pair[1].get("description", "")),
                len(normalize_spaces(pair[1].get("description", ""))),
                -pair[0],
            ),
        )
        winners.append(winner)

    winners.sort(key=lambda pair: pair[0])
    return [item for _, item in winners], duplicates_removed


def looks_like_end_marker_line(line: str) -> bool:
    lowered = normalize_spaces(line).lower()
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


def should_stop_after_marker(current_line: str, lookahead_window: str) -> bool:
    """
    Composite end-of-agenda detector.
    """
    line = normalize_spaces(current_line).lower()
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
