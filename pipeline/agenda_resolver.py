from __future__ import annotations

import logging

from pipeline.agenda_legistar import fetch_legistar_agenda_items
from pipeline.agenda_resolver_contracts import (
    AgendaDocumentQuery,
    AgendaExtractor,
    AgendaItemRecord,
    AgendaResolverSession,
    CatalogLike,
    DocumentLike,
    EventLike,
    PlaceLike,
    ResolvedAgendaPayload,
)
from pipeline.agenda_resolver_enrichment import _apply_page_numbers_from_reference
from pipeline.agenda_resolver_html import _best_html_items_for_event as _best_html_items_for_event_impl
from pipeline.agenda_resolver_legistar_policy import (
    _LEGISTAR_NOTICE_PATTERNS,
    _LEGISTAR_PROCEDURAL_PATTERNS,
    _LEGISTAR_SECTION_WRAPPER_TITLES,
    _filter_legistar_items,
    _legistar_items_are_acceptable,
)
from pipeline.agenda_resolver_quality import (
    _get_value,
    _normalize_title,
    agenda_items_look_low_quality,
    agenda_quality_score,
)
from pipeline.agenda_resolver_runner import (
    has_viable_structured_agenda_source as _has_viable_structured_agenda_source_impl,
)
from pipeline.agenda_resolver_runner import (
    resolve_agenda_items as _resolve_agenda_items_impl,
)


logger = logging.getLogger("agenda-resolver")

__all__ = (
    "AgendaItemRecord",
    "ResolvedAgendaPayload",
    "AgendaExtractor",
    "CatalogLike",
    "PlaceLike",
    "EventLike",
    "DocumentLike",
    "AgendaDocumentQuery",
    "AgendaResolverSession",
    "_get_value",
    "_normalize_title",
    "_LEGISTAR_NOTICE_PATTERNS",
    "_LEGISTAR_PROCEDURAL_PATTERNS",
    "_LEGISTAR_SECTION_WRAPPER_TITLES",
    "agenda_quality_score",
    "agenda_items_look_low_quality",
    "_filter_legistar_items",
    "_legistar_items_are_acceptable",
    "_best_html_items_for_event",
    "_apply_page_numbers_from_reference",
    "has_viable_structured_agenda_source",
    "resolve_agenda_items",
    "fetch_legistar_agenda_items",
    "logger",
)


def _best_html_items_for_event(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
) -> list[AgendaItemRecord]:
    return _best_html_items_for_event_impl(
        session,
        catalog,
        doc,
        quality_scorer=agenda_quality_score,
    )


def has_viable_structured_agenda_source(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
) -> bool:
    return _has_viable_structured_agenda_source_impl(
        session,
        catalog,
        doc,
        html_loader=_best_html_items_for_event,
        quality_scorer=agenda_quality_score,
        legistar_fetcher=fetch_legistar_agenda_items,
        legistar_filter=_filter_legistar_items,
        legistar_acceptance_checker=_legistar_items_are_acceptable,
    )


def resolve_agenda_items(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
    local_ai: AgendaExtractor,
) -> ResolvedAgendaPayload:
    return _resolve_agenda_items_impl(
        session,
        catalog,
        doc,
        local_ai,
        html_loader=_best_html_items_for_event,
        quality_scorer=agenda_quality_score,
        legistar_fetcher=fetch_legistar_agenda_items,
        legistar_filter=_filter_legistar_items,
        legistar_acceptance_checker=_legistar_items_are_acceptable,
        page_enricher=_apply_page_numbers_from_reference,
        logger=logger,
    )
