import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pipeline.config import (
    AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE,
    AGENDA_FALLBACK_MAX_ITEMS_PER_DOC,
    AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH,
    AGENDA_MIN_TITLE_CHARS,
    LLM_AGENDA_MAX_TEXT,
)
from pipeline.utils import is_likely_human_name


logger = logging.getLogger("local-ai")

_ITEM_HEADER_RE = re.compile(r"(?im)^\s*ITEM\s+(?P<order>\d+)\s*:\s*")
_PAGE_MARKER_RE = re.compile(r"\[PAGE\s+(\d+)\]", flags=re.IGNORECASE)
_INLINE_PAGE_HEADER_RE = re.compile(r"(?im)^.*\bPage\s+(\d+)\s*$")
_FALLBACK_PARAGRAPH_BOUNDARY_RE = re.compile(
    r"(?i)^\s*("
    r"subject\s*:"
    r"|item\s*#?\s*\d{1,3}\b"
    r"|#?\s*\d{1,2}(?:\.\d+)?[\.\):]\s+"
    r"|[A-Z][A-Z\s]{12,}"
    r")"
)
_NUMBERED_LINE_PATTERN = re.compile(
    r"(?m)^\s*(?:item\s*)?#?\s*(\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+(.{6,400})$"
)
_WRAPPED_TITLE_BOUNDARY_RE = re.compile(
    r"(?i)^\s*(from|recommendation|recommended action|financial implications|contact|vote|result|action|subject)\s*:"
)
_WRAPPED_TITLE_LIST_ITEM_RE = re.compile(
    r"^\s*(?:item\s*)?#?\s*(\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+"
)
_DATE_LINE_RE = re.compile(r"^[A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}$")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|am|pm)\b")
_ADDRESS_RE = re.compile(r"\b\d{2,6}\s+[A-Za-z].*(street|st|avenue|ave|road|rd|blvd|boulevard)\b")
_IP_ADDRESS_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_ACCESSIBILITY_RE = re.compile(r"\b(disability[- ]related|accommodation\(s\)|auxiliary aids|interpreters?)\b")
_BROWN_ACT_RE = re.compile(r"\b(brown act|executive orders?)\b")
_COMMUNICATION_ACCESS_RE = re.compile(r"\b(communication access information|questions regarding|public comment portion)\b")
_AGENDA_REPORTS_RE = re.compile(r"\b(agendas? and agenda reports?|agenda reports? may be accessed)\b")
_PUBLIC_COMMENT_RE = re.compile(r"\b(may participate in the public comment|meeting will be conducted in accordance)\b")
_BERKELEY_CITY_CLERK_RE = re.compile(r"\b(city clerk|cityofberkeley\.info|cityofberkeley\.org)\b")
_DISTRICT_RE = re.compile(r"^district\s+\d+\b")
_RECOMMENDATION_SUBITEM_RE = re.compile(r"\d{1,2}[A-Za-z]")
_VOTE_RE = re.compile(r"(?im)\bVote:\s*([^\n\r]+)")
_EXTRACTION_OPERATION_LABEL = "AI Agenda Extraction"
_EXTRACTION_COUNTERS_LOG = (
    "agenda_segmentation.counters mode=%s accepted_items_final=%s rejected_procedural=%s "
    "rejected_contact=%s rejected_low_substance=%s rejected_lowercase_fragment=%s "
    "rejected_notice_fragment=%s rejected_tabular_fragment=%s rejected_nested_subitem=%s "
    "context_carryover_pages=%s stop_marker_candidates=%s stopped_after_end_marker=%s "
    "rejected_noise=%s deduped_toc_duplicates=%s"
)


@dataclass(frozen=True)
class AgendaExtractionHelpers:
    normalize_spaces: Callable[[str], str]
    is_probable_line_fragment_title: Callable[[str], bool]
    is_procedural_noise_title: Callable[[str], bool]
    is_contact_or_letterhead_noise: Callable[[str, str], bool]
    looks_like_teleconference_endpoint_line: Callable[[str], bool]
    looks_like_agenda_segmentation_boilerplate: Callable[[str], bool]
    is_tabular_fragment: Callable[[str, str, dict | None], bool]
    should_accept_llm_item: Callable[[dict, str], bool]
    dedupe_agenda_items_for_document: Callable[[list[dict]], tuple[list[dict], int]]
    looks_like_end_marker_line: Callable[[str], bool]
    should_stop_after_marker: Callable[[str, str], bool]


def build_agenda_extraction_prompt(text: str, *, max_text: int = LLM_AGENDA_MAX_TEXT) -> str:
    """
    Preserve the current extraction prompt contract while centralizing prompt assembly.
    """
    safe_text = (text or "")[:max_text]
    return (
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


def reconstruct_llm_agenda_content(raw_content: str) -> str:
    """
    Restore the leading ITEM marker only when the continuation clearly followed the prompt shape.
    """
    if (
        "(page" in raw_content.lower()
        or re.search(r"(?im)^\s*ITEM\s+\d+\s*:", raw_content)
        or re.search(r"(?im)\n\s*ITEM\s+\d+\s*:", raw_content)
    ):
        return "ITEM 1:" + raw_content
    return raw_content


def parse_llm_agenda_items(llm_text: str) -> list[dict]:
    """
    Parse agenda items from the provider text while preserving multiline descriptions.
    """
    text = (llm_text or "").strip()
    if not text:
        return []

    headers = list(_ITEM_HEADER_RE.finditer(text))
    if not headers:
        return []

    out: list[dict] = []
    for index, match in enumerate(headers):
        try:
            order = int(match.group("order"))
        except (TypeError, ValueError):
            continue

        start = match.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        if not body:
            continue

        page_match = re.search(r"(?i)\(\s*page\s*(\d+)\s*\)", body)
        page_number = 1
        title_part = body
        description_part = ""
        if page_match:
            try:
                page_number = int(page_match.group(1))
            except (TypeError, ValueError):
                page_number = 1
            title_part = body[: page_match.start()].strip()
            description_part = body[page_match.end() :].strip()
        else:
            separator = re.search(r"\s+[-\u2013\u2014:]\s+", body)
            if separator:
                title_part = body[: separator.start()].strip()
                description_part = body[separator.end() :].strip()
            else:
                first_line, *rest = body.splitlines()
                title_part = first_line.strip()
                description_part = " ".join(line.strip() for line in rest).strip()

        title = " ".join((title_part or "").split())
        if not title:
            continue

        description = (description_part or "").strip()
        description = re.sub(r"^[-\u2013\u2014:]\s*", "", description)
        description = " ".join(description.split())
        out.append(
            {
                "order": order,
                "title": title,
                "page_number": page_number,
                "description": description,
            }
        )

    seen: set[tuple[int, str]] = set()
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
    Build paragraph-like chunks for the weakest heuristic fallback.
    """
    raw = (page_content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return []

    blank_paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", raw) if paragraph.strip()]
    if len(blank_paragraphs) >= 3:
        return blank_paragraphs

    paragraphs: list[str] = []
    current_lines: list[str] = []
    for line in [line.strip() for line in raw.splitlines()]:
        if not line:
            if current_lines:
                paragraphs.append("\n".join(current_lines).strip())
                current_lines = []
            continue
        if _FALLBACK_PARAGRAPH_BOUNDARY_RE.match(line) and current_lines:
            paragraphs.append("\n".join(current_lines).strip())
            current_lines = [line]
            continue
        current_lines.append(line)
    if current_lines:
        paragraphs.append("\n".join(current_lines).strip())
    return [paragraph for paragraph in paragraphs if paragraph]


def run_agenda_extraction_pipeline(
    *,
    text: str,
    raw_provider_content: str | None,
    mode: str,
    helpers: AgendaExtractionHelpers,
) -> list[dict]:
    context = _AgendaExtractionContext(mode=mode, helpers=helpers)
    if raw_provider_content:
        context.accept_provider_output(raw_provider_content)
    if not context.items:
        context.run_fallback(text)
    return context.finalize()


@dataclass
class _AgendaExtractionContext:
    mode: str
    helpers: AgendaExtractionHelpers
    items: list[dict] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: {
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
    })
    parse_state: dict[str, Any] = field(default_factory=lambda: {
        "active_parent_item": None,
        "active_parent_page": None,
        "parent_context_confidence": 0.0,
        "seen_top_level_items": 0,
    })

    def accept_provider_output(self, raw_provider_content: str) -> None:
        content = reconstruct_llm_agenda_content(raw_provider_content)
        for parsed_item in parse_llm_agenda_items(content):
            self.add_item(
                parsed_item["order"],
                parsed_item["title"],
                parsed_item["page_number"],
                parsed_item["description"],
                source_type="llm",
                context={"has_active_parent": False},
            )

    def run_fallback(self, text: str) -> None:
        page_chunks = self.split_text_by_page_markers(text)
        for page_index, (page_number, page_content) in enumerate(page_chunks):
            if self.parse_state["active_parent_item"] is not None and page_index > 0:
                previous_page_number = page_chunks[page_index - 1][0]
                if previous_page_number != page_number:
                    self.stats["context_carryover_pages"] += 1

            trailing_text = "\n".join(chunk for _, chunk in page_chunks[page_index:])
            page_content, stop_after_page = self.truncate_page_after_end_marker(page_content, trailing_text)
            speaker_context = self._speaker_context(page_content)
            numbered_lines = list(_NUMBERED_LINE_PATTERN.finditer(page_content))

            if numbered_lines:
                numbered_lines = self._filter_noise_numbered_block(numbered_lines, page_content, page_number)
                if numbered_lines:
                    self._consume_numbered_lines(numbered_lines, page_content, page_number, speaker_context)
                    if len(self.items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC or stop_after_page:
                        break
                    continue

            self._consume_paragraph_fallback(page_content, page_number)
            if len(self.items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC or stop_after_page:
                break

    def finalize(self) -> list[dict]:
        self.items, deduped = self.helpers.dedupe_agenda_items_for_document(self.items)
        self.stats["deduped_toc_duplicates"] = deduped
        self.stats["accepted_items_final"] = len(self.items)
        logger.info(
            _EXTRACTION_COUNTERS_LOG,
            self.mode,
            self.stats["accepted_items_final"],
            self.stats["rejected_procedural"],
            self.stats["rejected_contact"],
            self.stats["rejected_low_substance"],
            self.stats["rejected_lowercase_fragment"],
            self.stats["rejected_notice_fragment"],
            self.stats["rejected_tabular_fragment"],
            self.stats["rejected_nested_subitem"],
            self.stats["context_carryover_pages"],
            self.stats["stop_marker_candidates"],
            self.stats["stopped_after_end_marker"],
            self.stats["rejected_noise"],
            self.stats["deduped_toc_duplicates"],
        )
        return self.items

    def add_item(
        self,
        order: int,
        title: str,
        page_number: int,
        description: str,
        *,
        result: str = "",
        source_type: str = "fallback",
        context: dict | None = None,
    ) -> None:
        clean_title = self.helpers.normalize_spaces(title)
        clean_description = self.helpers.normalize_spaces(description) if description else ""
        if source_type == "fallback" and self.helpers.is_probable_line_fragment_title(clean_title):
            self.stats["rejected_lowercase_fragment"] += 1
            return
        if self.helpers.is_tabular_fragment(clean_title, clean_description, context):
            self.stats["rejected_tabular_fragment"] += 1
            return
        if self.helpers.looks_like_agenda_segmentation_boilerplate(clean_title):
            self.stats["rejected_notice_fragment"] += 1
            return
        if self.is_noise_title(clean_title):
            self.stats["rejected_noise"] += 1
            return

        if source_type == "llm":
            if self.helpers.is_procedural_noise_title(clean_title):
                self.stats["rejected_procedural"] += 1
                return
            if self.helpers.is_contact_or_letterhead_noise(clean_title, clean_description):
                self.stats["rejected_contact"] += 1
                return
            if not self.helpers.should_accept_llm_item(
                {
                    "title": clean_title,
                    "description": clean_description,
                    "page_number": page_number,
                    "context": context or {},
                },
                self.mode,
            ):
                self.stats["rejected_low_substance"] += 1
                return

        self.items.append(
            {
                "order": order,
                "title": clean_title,
                "page_number": page_number,
                "description": clean_description,
                "classification": "Agenda Item",
                "result": self.helpers.normalize_spaces(result),
            }
        )

    def is_noise_title(self, title: str) -> bool:
        lowered = self.helpers.normalize_spaces(title).lower()
        if not lowered or len(lowered) < AGENDA_MIN_TITLE_CHARS:
            return True
        if self.helpers.is_procedural_noise_title(lowered):
            return True
        if self.helpers.is_contact_or_letterhead_noise(lowered, ""):
            return True
        if _IP_ADDRESS_RE.search(lowered):
            return True
        if self.helpers.looks_like_teleconference_endpoint_line(lowered):
            return True
        if re.search(r"\b(us west|us east)\b", lowered):
            return True
        if self.looks_like_spaced_ocr(lowered):
            return True
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return True
        if "http://" in lowered or "https://" in lowered or "www." in lowered:
            return True
        if _DATE_LINE_RE.match(title):
            return True
        if _TIME_RE.search(lowered):
            return True
        if _ADDRESS_RE.search(lowered):
            return True
        if "mayor" in lowered or "councilmembers" in lowered:
            return True
        if self.helpers.looks_like_agenda_segmentation_boilerplate(lowered):
            return True
        if _ACCESSIBILITY_RE.search(lowered):
            return True
        if _BROWN_ACT_RE.search(lowered):
            return True
        if _COMMUNICATION_ACCESS_RE.search(lowered):
            return True
        if _AGENDA_REPORTS_RE.search(lowered):
            return True
        if _PUBLIC_COMMENT_RE.search(lowered):
            return True
        if _BERKELEY_CITY_CLERK_RE.search(lowered):
            return True
        if "as follows" in lowered and len(lowered) <= 40:
            return True
        if lowered.endswith(":") and len(lowered) <= 45:
            return True
        if any(
            token in lowered
            for token in (
                "special closed meeting",
                "calling a special meeting",
                "agenda packet",
                "table of contents",
                "supplemental communications",
                "form letters",
            )
        ):
            return True
        if "government code section 84308" in lowered or "levine act" in lowered:
            return True
        if "parties to a proceeding involving a license, permit, or other" in lowered:
            return True
        return bool(_DISTRICT_RE.match(lowered))

    def looks_like_spaced_ocr(self, value: str) -> bool:
        tokens = [token for token in self.helpers.normalize_spaces(value).split(" ") if token]
        if not tokens:
            return False
        single_char_tokens = sum(1 for token in tokens if len(token) == 1 and token.isalpha())
        return (single_char_tokens / len(tokens)) >= 0.6

    def is_probable_person_name(self, value: str) -> bool:
        clean = self.helpers.normalize_spaces(value)
        if not clean:
            return False
        clean = re.sub(r"\(\d+\)", "", clean).strip()
        lowered = clean.lower()
        if "on behalf of" in lowered:
            return True
        if re.search(
            r"\b(update|plan|zoning|hearing|budget|report|session|meeting|ordinance|resolution|project|communications|adjournment|amendment|specific|corridor|worksession)\b",
            lowered,
        ):
            return False
        if is_likely_human_name(clean, allow_single_word=True):
            return True
        if " and " in lowered or " & " in clean:
            tokens = re.split(r"\s+(?:and|&)\s+|\s+", clean)
            tokens = [token for token in tokens if token]
            if 2 <= len(tokens) <= 8 and all(re.match(r"^[A-Z][A-Za-z'’\.\-]*$", token) for token in tokens):
                return True
        return False

    def merge_wrapped_title_lines(self, base_title: str, block_text: str) -> str:
        title = self.helpers.normalize_spaces(base_title)
        if not block_text:
            return title

        added = 0
        for raw_line in (block_text or "").splitlines():
            line = raw_line.strip()
            if not line:
                if added > 0:
                    break
                continue
            if _WRAPPED_TITLE_BOUNDARY_RE.match(line) or _WRAPPED_TITLE_LIST_ITEM_RE.match(line):
                break
            if len(line) < 3:
                break
            title = self.helpers.normalize_spaces(f"{title} {line}")
            added += 1
            if added >= 2:
                break
        return title

    def split_text_by_page_markers(self, raw_text: str) -> list[tuple[int, str]]:
        markers: list[tuple[int, int]] = []
        for match in _PAGE_MARKER_RE.finditer(raw_text):
            markers.append((match.start(), int(match.group(1))))
        for match in _INLINE_PAGE_HEADER_RE.finditer(raw_text):
            markers.append((match.start(), int(match.group(1))))

        if not markers:
            return [(1, raw_text)]

        markers.sort(key=lambda item: item[0])
        deduped_markers: list[tuple[int, int]] = []
        for position, page_number in markers:
            if (
                deduped_markers
                and deduped_markers[-1][1] == page_number
                and (position - deduped_markers[-1][0]) < 120
            ):
                continue
            deduped_markers.append((position, page_number))

        chunks: list[tuple[int, str]] = []
        for index, (start_position, page_number) in enumerate(deduped_markers):
            end_position = deduped_markers[index + 1][0] if index + 1 < len(deduped_markers) else len(raw_text)
            chunk = raw_text[start_position:end_position].strip()
            if chunk:
                chunks.append((page_number, chunk))
        return chunks or [(1, raw_text)]

    def truncate_page_after_end_marker(self, page_content: str, trailing_text: str) -> tuple[str, bool]:
        truncated_page_content = page_content
        stop_after_page = False
        lines = page_content.splitlines(keepends=True)
        cursor = 0
        for line_index, raw_line in enumerate(lines):
            candidate_line = raw_line.strip()
            line_length = len(raw_line)
            if not self.helpers.looks_like_end_marker_line(candidate_line):
                cursor += line_length
                continue
            self.stats["stop_marker_candidates"] += 1
            lookahead_window = "".join(lines[line_index : line_index + 25]) + "\n" + trailing_text[:2500]
            if self.helpers.should_stop_after_marker(candidate_line, lookahead_window):
                truncated_page_content = page_content[:cursor]
                self.stats["stopped_after_end_marker"] += 1
                stop_after_page = True
                break
            cursor += line_length
        return truncated_page_content, stop_after_page

    def _speaker_context(self, page_content: str) -> bool:
        page_lower = page_content.lower()
        return (
            "communications" in page_lower
            or "speakers" in page_lower
            or "public comment" in page_lower
            or "item #1" in page_lower
            or "item #2" in page_lower
        )

    def _filter_noise_numbered_block(
        self,
        numbered_lines: list[re.Match[str]],
        page_content: str,
        page_number: int,
    ) -> list[re.Match[str]]:
        person_like_count = sum(1 for match in numbered_lines if self.is_probable_person_name(match.group(2).strip()))
        person_heavy_numbered_list = len(numbered_lines) >= 5 and (person_like_count / len(numbered_lines)) >= 0.5
        noise_like_count = sum(
            1
            for match in numbered_lines
            if self.is_noise_title(match.group(2).strip())
            or self.helpers.looks_like_agenda_segmentation_boilerplate(match.group(2).strip())
        )
        mostly_noise_numbered_list = len(numbered_lines) >= 4 and (noise_like_count / len(numbered_lines)) >= 0.5
        if mostly_noise_numbered_list:
            logger.debug(
                "agenda_segmentation.skip_numbered_block",
                extra={
                    "page": page_number,
                    "numbered_lines": len(numbered_lines),
                    "noise_like": noise_like_count,
                },
            )
            return []
        self.parse_state["person_heavy_numbered_list"] = person_heavy_numbered_list
        self.parse_state["page_content"] = page_content
        return numbered_lines

    def _consume_numbered_lines(
        self,
        numbered_lines: list[re.Match[str]],
        page_content: str,
        page_number: int,
        speaker_context: bool,
    ) -> None:
        person_heavy_numbered_list = bool(self.parse_state.get("person_heavy_numbered_list"))
        for index, match in enumerate(numbered_lines):
            marker = match.group(1)
            title = match.group(2).strip()
            marker_normalized = (marker or "").strip()
            marker_upper = marker_normalized.upper()
            is_top_level_numeric = bool(re.fullmatch(r"\d{1,2}(?:\.\d+)?", marker_normalized))
            preceding_window = page_content[max(0, match.start() - 500):match.start()].lower()
            looks_like_nested_numeric_recommendation = bool(
                self.parse_state["active_parent_item"]
                and is_top_level_numeric
                and "recommendation:" in preceding_window
                and ("would:" in preceding_window or "following action" in preceding_window)
                and "subject:" not in preceding_window[-160:]
            )
            is_contextual_subitem = bool(
                self.parse_state["active_parent_item"]
                and (
                    re.fullmatch(r"[A-Z]", marker_upper)
                    or re.fullmatch(r"[IVXLC]+", marker_upper)
                    or re.fullmatch(_RECOMMENDATION_SUBITEM_RE, marker_normalized)
                    or looks_like_nested_numeric_recommendation
                )
            )
            if is_contextual_subitem:
                self.stats["rejected_nested_subitem"] += 1
                continue
            if self.is_probable_person_name(title) and (speaker_context or person_heavy_numbered_list):
                continue
            if self.helpers.is_procedural_noise_title(title):
                continue
            if self.helpers.is_contact_or_letterhead_noise(title, ""):
                continue

            block_start = match.end()
            block_end = numbered_lines[index + 1].start() if index + 1 < len(numbered_lines) else len(page_content)
            block_text = page_content[block_start:block_end]
            title = self.merge_wrapped_title_lines(title, block_text)
            vote_match = _VOTE_RE.search(block_text)
            vote_result = vote_match.group(1) if vote_match else ""

            before_count = len(self.items)
            self.add_item(
                len(self.items) + 1,
                title,
                page_number,
                f"Agenda section {marker}",
                result=vote_result,
                context={
                    "has_active_parent": self.parse_state["active_parent_item"] is not None,
                    "parent_context_confidence": self.parse_state["parent_context_confidence"],
                    "seen_top_level_items": self.parse_state["seen_top_level_items"],
                },
            )
            if len(self.items) > before_count and is_top_level_numeric:
                self.parse_state["active_parent_item"] = self.helpers.normalize_spaces(title)
                self.parse_state["active_parent_page"] = page_number
                self.parse_state["parent_context_confidence"] = 1.0
                self.parse_state["seen_top_level_items"] += 1
            if len(self.items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC:
                break

    def _consume_paragraph_fallback(self, page_content: str, page_number: int) -> None:
        paragraphs = [
            paragraph
            for paragraph in iter_fallback_paragraphs(page_content)
            if 10 < len(paragraph.strip()) < 1000
        ]

        added_from_paragraphs = 0
        consecutive_rejects = 0
        for paragraph in paragraphs:
            if len(self.items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC:
                break
            if added_from_paragraphs >= AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH:
                break

            lines = paragraph.split("\n")
            if not lines:
                consecutive_rejects += 1
                if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                    break
                continue

            title = re.sub(r"^\s*\d+(?:\.\d+)?[\.\):]?\s*", "", lines[0].strip())
            title_lowered = title.lower()
            if not (10 < len(title) < 150):
                consecutive_rejects += 1
                if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                    break
                continue
            if any(blocker in title_lowered for blocker in ("page", "packet", "continuing")):
                consecutive_rejects += 1
                if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                    break
                continue
            if title_lowered.startswith("item #") or self.is_probable_person_name(title):
                consecutive_rejects += 1
                if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                    break
                continue

            description = (paragraph[:500] + "...") if len(paragraph) > 500 else paragraph
            before_count = len(self.items)
            self.add_item(
                len(self.items) + 1,
                title,
                page_number,
                description,
                context={
                    "has_active_parent": self.parse_state["active_parent_item"] is not None,
                    "parent_context_confidence": self.parse_state["parent_context_confidence"],
                    "seen_top_level_items": self.parse_state["seen_top_level_items"],
                },
            )
            if len(self.items) > before_count:
                added_from_paragraphs += 1
                consecutive_rejects = 0
            else:
                consecutive_rejects += 1
                if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                    break
