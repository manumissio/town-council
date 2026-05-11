from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from pipeline.agenda_extraction_acceptance import accept_agenda_item
from pipeline.agenda_extraction_diagnostics import (
    AgendaExtractionStats,
    AgendaParseState,
    log_agenda_extraction_counters,
)
from pipeline.agenda_extraction_noise import (
    is_probable_person_name,
    merge_wrapped_title_lines,
)
from pipeline.agenda_extraction_numbered import (
    NUMBERED_LINE_PATTERN,
    TOP_LEVEL_NUMERIC_RE,
    VOTE_RE,
    is_contextual_subitem,
    numbered_title_is_noise,
)
from pipeline.agenda_extraction_paragraphs import (
    candidate_paragraphs,
    paragraph_description,
    paragraph_progress,
    paragraph_title,
    reject_paragraph_title,
)
from pipeline.agenda_extraction_pages import (
    page_has_speaker_context,
    split_text_by_page_markers,
    truncate_page_after_end_marker,
)
from pipeline.agenda_extraction_parser import (
    AgendaItemPayload,
    parse_llm_agenda_items,
    reconstruct_llm_agenda_content,
)
from pipeline.agenda_text_heuristics import (
    dedupe_agenda_items_for_document,
    is_contact_or_letterhead_noise,
    is_procedural_noise_title,
    normalize_spaces,
)
from pipeline.config import (
    AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE,
    AGENDA_FALLBACK_MAX_ITEMS_PER_DOC,
    AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH,
)


@dataclass(slots=True)
class AgendaExtractionContext:
    mode: str
    logger: logging.Logger
    items: list[AgendaItemPayload] = field(default_factory=list)
    stats: AgendaExtractionStats = field(default_factory=AgendaExtractionStats)
    parse_state: AgendaParseState = field(default_factory=AgendaParseState)

    def accept_provider_output(self, raw_provider_content: str) -> None:
        content = reconstruct_llm_agenda_content(raw_provider_content)
        for parsed_item in parse_llm_agenda_items(content):
            self.add_item(
                int(parsed_item["order"]),
                str(parsed_item["title"]),
                int(parsed_item["page_number"]),
                str(parsed_item["description"]),
                source_type="llm",
                context={"has_active_parent": False},
            )

    def run_fallback(self, text: str) -> None:
        page_chunks = split_text_by_page_markers(text)
        for page_index, (page_number, page_content) in enumerate(page_chunks):
            self._record_parent_context_carryover(page_index, page_number, page_chunks)
            trailing_text = "\n".join(chunk for _, chunk in page_chunks[page_index:])
            page_content, stop_after_page = truncate_page_after_end_marker(page_content, trailing_text, self.stats)
            if self._consume_page_numbered_lines(page_content, page_number):
                if self._should_stop_fallback(stop_after_page):
                    break
                continue
            self._consume_paragraph_fallback(page_content, page_number)
            if self._should_stop_fallback(stop_after_page):
                break

    def finalize(self) -> list[AgendaItemPayload]:
        self.items, deduped = dedupe_agenda_items_for_document(self.items)
        self.stats.deduped_toc_duplicates = deduped
        self.stats.accepted_items_final = len(self.items)
        log_agenda_extraction_counters(self.logger, mode=self.mode, stats=self.stats)
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
        context: dict[str, object] | None = None,
    ) -> None:
        clean_title = normalize_spaces(title)
        clean_description = normalize_spaces(description) if description else ""
        if not accept_agenda_item(
            clean_title,
            clean_description,
            page_number,
            source_type,
            context,
            mode=self.mode,
            stats=self.stats,
        ):
            return
        self.items.append(
            {
                "order": order,
                "title": clean_title,
                "page_number": page_number,
                "description": clean_description,
                "classification": "Agenda Item",
                "result": normalize_spaces(result),
            }
        )

    def _record_parent_context_carryover(
        self,
        page_index: int,
        page_number: int,
        page_chunks: list[tuple[int, str]],
    ) -> None:
        if self.parse_state.active_parent_item is None or page_index <= 0:
            return
        previous_page_number = page_chunks[page_index - 1][0]
        if previous_page_number != page_number:
            self.stats.context_carryover_pages += 1

    def _consume_page_numbered_lines(self, page_content: str, page_number: int) -> bool:
        numbered_lines = list(NUMBERED_LINE_PATTERN.finditer(page_content))
        if not numbered_lines:
            return False
        numbered_lines = self._filter_noise_numbered_block(numbered_lines, page_number)
        if not numbered_lines:
            return False
        self._consume_numbered_lines(numbered_lines, page_content, page_number, page_has_speaker_context(page_content))
        return True

    def _filter_noise_numbered_block(
        self,
        numbered_lines: list[re.Match[str]],
        page_number: int,
    ) -> list[re.Match[str]]:
        person_like_count = sum(1 for match in numbered_lines if is_probable_person_name(match.group(2).strip()))
        self.parse_state.person_heavy_numbered_list = len(numbered_lines) >= 5 and (
            person_like_count / len(numbered_lines)
        ) >= 0.5
        noise_like_count = sum(1 for match in numbered_lines if self._numbered_title_is_noise(match.group(2).strip()))
        if len(numbered_lines) >= 4 and (noise_like_count / len(numbered_lines)) >= 0.5:
            self.logger.debug(
                "agenda_segmentation.skip_numbered_block",
                extra={"page": page_number, "numbered_lines": len(numbered_lines), "noise_like": noise_like_count},
            )
            return []
        return numbered_lines

    def _consume_numbered_lines(
        self,
        numbered_lines: list[re.Match[str]],
        page_content: str,
        page_number: int,
        speaker_context: bool,
    ) -> None:
        for index, match in enumerate(numbered_lines):
            if self._skip_numbered_line(match, page_content, speaker_context):
                continue
            self._add_numbered_line_item(index, match, numbered_lines, page_content, page_number)
            if len(self.items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC:
                break

    def _skip_numbered_line(self, match: re.Match[str], page_content: str, speaker_context: bool) -> bool:
        marker = (match.group(1) or "").strip()
        title = match.group(2).strip()
        if self._is_contextual_subitem(marker, page_content, match.start()):
            self.stats.rejected_nested_subitem += 1
            return True
        if is_probable_person_name(title) and (speaker_context or self.parse_state.person_heavy_numbered_list):
            return True
        return is_procedural_noise_title(title) or is_contact_or_letterhead_noise(title, "")

    def _add_numbered_line_item(
        self,
        index: int,
        match: re.Match[str],
        numbered_lines: list[re.Match[str]],
        page_content: str,
        page_number: int,
    ) -> None:
        marker = (match.group(1) or "").strip()
        title = match.group(2).strip()
        block_start = match.end()
        block_end = numbered_lines[index + 1].start() if index + 1 < len(numbered_lines) else len(page_content)
        block_text = page_content[block_start:block_end]
        vote_match = VOTE_RE.search(block_text)
        before_count = len(self.items)
        clean_title = merge_wrapped_title_lines(title, block_text)
        self.add_item(
            len(self.items) + 1,
            clean_title,
            page_number,
            f"Agenda section {marker}",
            result=vote_match.group(1) if vote_match else "",
            context=self.parse_state.item_context(),
        )
        if len(self.items) > before_count and TOP_LEVEL_NUMERIC_RE.fullmatch(marker):
            self._remember_parent_item(clean_title, page_number)

    def _consume_paragraph_fallback(self, page_content: str, page_number: int) -> None:
        added_from_paragraphs = 0
        consecutive_rejects = 0
        for paragraph in candidate_paragraphs(page_content):
            if self._stop_paragraph_fallback(added_from_paragraphs):
                break
            title = paragraph_title(paragraph)
            if reject_paragraph_title(title) or is_probable_person_name(title):
                consecutive_rejects += 1
                if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                    break
                continue
            before_count = len(self.items)
            self.add_item(
                len(self.items) + 1,
                title,
                page_number,
                paragraph_description(paragraph),
                context=self.parse_state.item_context(),
            )
            added_from_paragraphs, consecutive_rejects = paragraph_progress(
                before_count,
                len(self.items),
                added_from_paragraphs,
                consecutive_rejects,
            )
            if consecutive_rejects >= AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE:
                break

    def _numbered_title_is_noise(self, title: str) -> bool:
        return numbered_title_is_noise(title)

    def _is_contextual_subitem(self, marker: str, page_content: str, position: int) -> bool:
        return is_contextual_subitem(
            marker,
            page_content,
            position,
            active_parent_item=self.parse_state.active_parent_item,
        )

    def _remember_parent_item(self, title: str, page_number: int) -> None:
        self.parse_state.active_parent_item = normalize_spaces(title)
        self.parse_state.active_parent_page = page_number
        self.parse_state.parent_context_confidence = 1.0
        self.parse_state.seen_top_level_items += 1

    def _should_stop_fallback(self, stop_after_page: bool) -> bool:
        return len(self.items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC or stop_after_page

    def _stop_paragraph_fallback(self, added_from_paragraphs: int) -> bool:
        return (
            len(self.items) >= AGENDA_FALLBACK_MAX_ITEMS_PER_DOC
            or added_from_paragraphs >= AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH
        )


def run_agenda_extraction_pipeline(
    *,
    text: str,
    raw_provider_content: str | None,
    mode: str,
    logger: logging.Logger,
) -> list[AgendaItemPayload]:
    context = AgendaExtractionContext(mode=mode, logger=logger)
    if raw_provider_content:
        context.accept_provider_output(raw_provider_content)
    if not context.items:
        context.run_fallback(text)
    return context.finalize()
