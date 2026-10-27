from __future__ import annotations

import re

from pipeline.agenda_extraction_diagnostics import AgendaParseState
from pipeline.agenda_extraction_noise import is_noise_title, is_probable_person_name
from pipeline.agenda_extraction_parser import ITEM_FIELD_PATTERN, RECORD_ID_PATTERN, iter_fallback_paragraphs
from pipeline.agenda_text_normalization import first_alpha_char, normalize_spaces


_PARAGRAPH_TITLE_PREFIX_RE = re.compile(r"^\s*\d+(?:\.\d+)?[\.)]\s+")
_PARAGRAPH_TITLE_BLOCKERS = ("page", "packet", "continuing")
_DOCUMENT_HEADER_RE = re.compile(
    r"^(?:meeting minutes|notice and agenda(?: - final)?|[a-z]+ \d{1,2}, \d{4}.*meeting minutes)$", re.IGNORECASE,
)
_BODY_LABEL_RE = re.compile(r"^(?:(?:city|town|county) council|.+ (?:commission|committee|board))$", re.IGNORECASE)
_HEADER_CLOCK_RE = re.compile(r"^\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\s*", re.IGNORECASE)
_HEADER_MEETING_RE = re.compile(
    r"^(?:telepresence meeting:|(?:special|regular) (?:council )?meeting\b)", re.IGNORECASE,
)
_PLACE_HEADER_RE = re.compile(r"^(?:city|town|county) of .+$", re.IGNORECASE)
_PAGE_FURNITURE_RE = re.compile(r"^page\s+\d+", re.IGNORECASE)
_APPLICANT_INTRO_RE = re.compile(r"\binterviewed the following applicants\b", re.IGNORECASE)
_APPLICANT_AFFILIATION_RE = re.compile(r"\b(?:commission|board|committee)\b", re.IGNORECASE)
_QUORUM_INTRO_RE = re.compile(r"\bquorum\b.*\bfollowing (?:meeting )?bodies\b", re.IGNORECASE)
_AFFILIATION_CONTINUATION_RE = re.compile(
    r"^(?:(?:[a-z]+\s+)*(?:commission|board|committee)\s*)?\(categor(?:y|ies)\b", re.IGNORECASE,
)
_RECESS_NOTE_RE = re.compile(r"^(?:council|commission|board) took a recess\b", re.IGNORECASE)
_BUSINESS_BODY_FIELDS = frozenset({"subject", "recommendation", "recommended action"})
_COMMUNITY_NOTICE_TITLE = "city council: community meeting notice"


def paragraph_is_document_furniture(paragraph: str, following: str, parse_state: AgendaParseState) -> bool:
    title = normalize_spaces(paragraph)
    if paragraph_has_record_anchor(paragraph) or any(
        match[1].lower() in _BUSINESS_BODY_FIELDS for match in ITEM_FIELD_PATTERN.finditer(paragraph)
    ):
        parse_state.paragraph_header_active = False
        parse_state.paragraph_list_context = None
        return False
    # A notice ends the preceding list without making the next topic header metadata.
    if title.lower() == _COMMUNITY_NOTICE_TITLE:
        parse_state.paragraph_list_context = None
        return True
    if _DOCUMENT_HEADER_RE.fullmatch(title):
        parse_state.paragraph_header_active = True
        return True
    if _PAGE_FURNITURE_RE.match(title):
        return True
    if parse_state.paragraph_header_active and _is_header_metadata(title, normalize_spaces(following)):
        return True
    parse_state.paragraph_header_active = False
    return _paragraph_is_list_material(paragraph, parse_state)


def _is_header_metadata(title: str, following: str) -> bool:
    if _BODY_LABEL_RE.fullmatch(title) or _is_header_schedule(title):
        return True
    return bool(_PLACE_HEADER_RE.fullmatch(title) and (
        _DOCUMENT_HEADER_RE.fullmatch(following) or _BODY_LABEL_RE.fullmatch(following)
        or _is_header_schedule(following)
    ))


def _is_header_schedule(title: str) -> bool:
    meeting_label = _HEADER_CLOCK_RE.sub("", title).lower()
    if _HEADER_MEETING_RE.match(meeting_label):
        return True
    # Validate the whole body label, not a substring of timed business.
    governing_body = meeting_label.removeprefix("special ").removeprefix("regular ").removesuffix(" meeting")
    return meeting_label.endswith(" meeting") and bool(
        governing_body == "council" or _BODY_LABEL_RE.fullmatch(governing_body)
    )


def _paragraph_is_list_material(paragraph: str, parse_state: AgendaParseState) -> bool:
    title = normalize_spaces(paragraph)
    # A list in the narrative sets context without erasing a preceding title.
    first_line_end = len(normalize_spaces(paragraph.splitlines()[0]))
    continuation_start = first_alpha_char(paragraph.partition("\n")[2])
    wrapped_intro = continuation_start is not None and continuation_start.islower()
    if title.lower() == "roll call" or re.match(r"(?i)^present:\s*\d", title):
        parse_state.paragraph_list_context = "attendance"
        return True
    applicant_intro = _APPLICANT_INTRO_RE.search(title)
    if applicant_intro:
        parse_state.paragraph_list_context = "applicants"
        return applicant_intro.start() < first_line_end or wrapped_intro
    quorum_intro = _QUORUM_INTRO_RE.search(title)
    if quorum_intro:
        parse_state.paragraph_list_context = "quorum"
        return quorum_intro.start() < first_line_end or wrapped_intro
    if parse_state.paragraph_list_context and _is_list_entry(title, parse_state.paragraph_list_context):
        return True
    parse_state.paragraph_list_context = None
    return title.lower() == "no speakers."


def _is_list_entry(title: str, list_context: str) -> bool:
    if is_noise_title(title) or _RECESS_NOTE_RE.match(title) or _AFFILIATION_CONTINUATION_RE.match(title):
        return True
    if list_context == "applicants" and re.match(r"(?i)^(?:commission|board|committee)\s*,", title):
        return True
    if list_context == "quorum":
        return bool(_BODY_LABEL_RE.fullmatch(title))
    person_title, separator, affiliation = title.partition(" - ")
    # A separator alone does not make a business title an applicant affiliation.
    if separator and not _APPLICANT_AFFILIATION_RE.search(affiliation):
        return False
    person_title = re.sub(r"\([^)]*\)", "", person_title).strip()
    # Mixed-case prose is not enough evidence to discard an independent topic.
    return person_title.istitle() and is_probable_person_name(person_title)


def candidate_paragraphs(page_content: str) -> list[str]:
    source_paragraphs = iter_fallback_paragraphs(page_content)
    paragraphs: list[str] = []
    for index, paragraph in enumerate(source_paragraphs):
        following = source_paragraphs[index + 1] if index + 1 < len(source_paragraphs) else ""
        # Check source neighbours before filtering can make distant headings adjacent.
        if (
            _PLACE_HEADER_RE.fullmatch(normalize_spaces(paragraph))
            and _DOCUMENT_HEADER_RE.fullmatch(normalize_spaces(following))
            and not paragraph_has_record_anchor(paragraph)
            and not ITEM_FIELD_PATTERN.search(paragraph)
        ):
            continue
        record_id = RECORD_ID_PATTERN.fullmatch(paragraph.strip())
        if record_id and index and _eligible_paragraph(source_paragraphs[index - 1]):
            paragraphs[-1] = _attach_record_id(paragraphs[-1], paragraph.strip())
        elif not record_id and _eligible_paragraph(paragraph):
            paragraphs.append(paragraph)
    return paragraphs


def _eligible_paragraph(paragraph: str) -> bool:
    return 10 < len(paragraph.strip()) < 1000 and not RECORD_ID_PATTERN.fullmatch(paragraph.strip())


def _attach_record_id(paragraph: str, record_id: str) -> str:
    # The source paragraph is a boundary; a later ID cannot justify crossing it.
    title_end = _paragraph_title_end(paragraph)
    if not paragraph[:title_end].strip():
        return f"{paragraph}\n{record_id}"
    title = paragraph[:title_end]
    body = f"\n{paragraph[title_end:]}" if title_end < len(paragraph) else ""
    return f"{normalize_spaces(title)}{body}\n{record_id}"


def paragraph_has_record_anchor(paragraph: str) -> bool:
    title_end = _paragraph_title_end(paragraph)
    if not paragraph[:title_end].strip():
        return False
    # A body-field mention is not evidence that the paragraph is an item title.
    return bool(RECORD_ID_PATTERN.search(paragraph[:title_end])) or any(
        RECORD_ID_PATTERN.fullmatch(line.strip()) for line in paragraph[title_end:].splitlines()
    )


def _paragraph_title_end(paragraph: str) -> int:
    leading_field = ITEM_FIELD_PATTERN.match(paragraph)
    start = leading_field.end() if leading_field and leading_field.group(1).lower() == "subject" else 0
    body_field = ITEM_FIELD_PATTERN.search(paragraph, start)
    return body_field.start() if body_field else len(paragraph)


def paragraph_title(paragraph: str) -> str:
    title_text = paragraph[:_paragraph_title_end(paragraph)]
    if not title_text.strip():
        return ""
    if paragraph_has_record_anchor(paragraph):
        title_lines = [line for line in title_text.splitlines() if not RECORD_ID_PATTERN.fullmatch(line.strip())]
        title = normalize_spaces(" ".join(title_lines))
        record_id = RECORD_ID_PATTERN.match(title)
        if record_id:
            return title[record_id.end():].strip()
        return _PARAGRAPH_TITLE_PREFIX_RE.sub("", title)
    lines = paragraph.splitlines()
    return _PARAGRAPH_TITLE_PREFIX_RE.sub("", lines[0].strip()) if lines else ""


def reject_paragraph_title(title: str) -> bool:
    title_lowered = title.lower()
    if not (10 < len(title) < 150):
        return True
    if any(blocker in title_lowered for blocker in _PARAGRAPH_TITLE_BLOCKERS):
        return True
    return title_lowered.startswith("item #")


def paragraph_description(paragraph: str) -> str:
    return (paragraph[:500] + "...") if len(paragraph) > 500 else paragraph


def paragraph_progress(before_count: int, after_count: int, added_count: int, reject_count: int) -> tuple[int, int]:
    if after_count > before_count:
        return added_count + 1, 0
    return added_count, reject_count + 1


def looks_like_nested_numeric_recommendation(page_content: str, position: int) -> bool:
    preceding_window = page_content[max(0, position - 500) : position].lower()
    return (
        "recommendation:" in preceding_window
        and ("would:" in preceding_window or "following action" in preceding_window)
        and "subject:" not in preceding_window[-160:]
    )
