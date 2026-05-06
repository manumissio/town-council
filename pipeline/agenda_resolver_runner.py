from __future__ import annotations

from datetime import date
import logging

from pipeline.agenda_crosscheck import merge_ai_with_eagenda
from pipeline.agenda_resolver_contracts import (
    AgendaExtractor,
    AgendaItemRecord,
    AgendaResolverSession,
    CatalogLike,
    DocumentLike,
    HtmlAgendaLoader,
    LegistarAcceptanceChecker,
    LegistarAgendaFetcher,
    LegistarFilter,
    PageNumberEnricher,
    QualityScorer,
    ResolvedAgendaPayload,
)


HTML_ACCEPTANCE_MIN_ITEMS = 2
HTML_ACCEPTANCE_MIN_SCORE = 55


def has_viable_structured_agenda_source(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
    *,
    html_loader: HtmlAgendaLoader,
    quality_scorer: QualityScorer,
    legistar_fetcher: LegistarAgendaFetcher,
    legistar_filter: LegistarFilter,
    legistar_acceptance_checker: LegistarAcceptanceChecker,
) -> bool:
    html_items = html_loader(session, catalog, doc)
    if len(html_items) >= HTML_ACCEPTANCE_MIN_ITEMS and quality_scorer(html_items) >= HTML_ACCEPTANCE_MIN_SCORE:
        return True

    legistar_client, event_date = _legistar_event_context(doc)
    legistar_items = legistar_fetcher(legistar_client, event_date)
    filtered_legistar_items = legistar_filter(legistar_items)
    return legistar_acceptance_checker(filtered_legistar_items)


def resolve_agenda_items(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
    local_ai: AgendaExtractor,
    *,
    html_loader: HtmlAgendaLoader,
    quality_scorer: QualityScorer,
    legistar_fetcher: LegistarAgendaFetcher,
    legistar_filter: LegistarFilter,
    legistar_acceptance_checker: LegistarAcceptanceChecker,
    page_enricher: PageNumberEnricher,
    logger: logging.Logger,
) -> ResolvedAgendaPayload:
    """
    Resolve agenda items in priority order:
    Legistar -> HTML -> LLM.
    """
    html_items = html_loader(session, catalog, doc)
    legistar_client, event_date = _legistar_event_context(doc)
    legistar_items = legistar_fetcher(legistar_client, event_date)
    filtered_legistar_items = legistar_filter(legistar_items)
    filtered_legistar_score = quality_scorer(filtered_legistar_items) if filtered_legistar_items else 0
    legistar_accepted = legistar_acceptance_checker(filtered_legistar_items)

    logger.info(
        "agenda_resolver_legistar catalog_location=%s raw_legistar_count=%s filtered_legistar_count=%s filtered_legistar_score=%s legistar_accepted=%s",
        getattr(catalog, "location", None),
        len(legistar_items),
        len(filtered_legistar_items),
        filtered_legistar_score,
        legistar_accepted,
    )

    if legistar_accepted:
        enriched = page_enricher(filtered_legistar_items, html_items)
        return _resolved_payload(
            items=enriched,
            source_used="legistar",
            quality_score=quality_scorer(enriched),
            confidence="high",
            llm_fallback_invoked=False,
            legistar_items=legistar_items,
            filtered_legistar_items=filtered_legistar_items,
            legistar_accepted=True,
        )

    if len(html_items) >= HTML_ACCEPTANCE_MIN_ITEMS and quality_scorer(html_items) >= HTML_ACCEPTANCE_MIN_SCORE:
        return _resolved_payload(
            items=html_items,
            source_used="html",
            quality_score=quality_scorer(html_items),
            confidence="medium",
            llm_fallback_invoked=False,
            legistar_items=legistar_items,
            filtered_legistar_items=filtered_legistar_items,
            legistar_accepted=False,
        )

    llm_items = local_ai.extract_agenda(catalog.content) if catalog and catalog.content else []
    merged = merge_ai_with_eagenda(llm_items, html_items)
    quality_score = quality_scorer(merged)
    logger.debug(
        "agenda_resolver_fallback source=llm catalog_location=%s html_candidates=%s merged_items=%s quality_score=%s",
        getattr(catalog, "location", None),
        len(html_items),
        len(merged),
        quality_score,
    )
    return _resolved_payload(
        items=merged,
        source_used="llm",
        quality_score=quality_score,
        confidence="medium" if merged else "low",
        llm_fallback_invoked=True,
        legistar_items=legistar_items,
        filtered_legistar_items=filtered_legistar_items,
        legistar_accepted=False,
    )


def _legistar_event_context(doc: DocumentLike | None) -> tuple[str | None, date | None]:
    if doc and doc.event and doc.event.place:
        return doc.event.place.legistar_client, doc.event.record_date
    return None, None


def _resolved_payload(
    *,
    items: list[AgendaItemRecord],
    source_used: str,
    quality_score: int,
    confidence: str,
    llm_fallback_invoked: bool,
    legistar_items: list[AgendaItemRecord],
    filtered_legistar_items: list[AgendaItemRecord],
    legistar_accepted: bool,
) -> ResolvedAgendaPayload:
    return {
        "items": items,
        "source_used": source_used,
        "quality_score": quality_score,
        "confidence": confidence,
        "llm_fallback_invoked": llm_fallback_invoked,
        "raw_legistar_count": len(legistar_items),
        "filtered_legistar_count": len(filtered_legistar_items),
        "legistar_accepted": legistar_accepted,
    }
