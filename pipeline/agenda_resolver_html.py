from __future__ import annotations

from collections.abc import Sequence

from pipeline.agenda_crosscheck import parse_eagenda_items_from_file
from pipeline.agenda_resolver_contracts import (
    AgendaItemRecord,
    AgendaResolverSession,
    CatalogLike,
    DocumentLike,
    QualityScorer,
)
from pipeline.agenda_resolver_quality import agenda_quality_score
from pipeline.models import Catalog, Document


def _best_html_items_for_event(
    session: AgendaResolverSession,
    catalog: CatalogLike,
    doc: DocumentLike | None,
    *,
    quality_scorer: QualityScorer = agenda_quality_score,
) -> list[AgendaItemRecord]:
    html_candidates: list[list[AgendaItemRecord]] = []
    if doc is None:
        return []

    if catalog.location and str(catalog.location).lower().endswith(".html"):
        html_candidates.append(parse_eagenda_items_from_file(catalog.location))

    event_documents: Sequence[Document] | list[Document]
    event = getattr(doc, "event", None)
    if event and getattr(event, "documents", None) is not None:
        event_documents = [
            event_doc
            for event_doc in (event.documents or [])
            if getattr(getattr(event_doc, "catalog", None), "location", "")
            and str(event_doc.catalog.location).lower().endswith(".html")
        ]
    else:
        event_documents = (
            session.query(Document)
            .join(Catalog, Document.catalog_id == Catalog.id)
            .filter(
                Document.event_id == doc.event_id,
                Catalog.location.like("%.html"),
            )
            .all()
        )

    for html_doc in event_documents:
        if html_doc.catalog and html_doc.catalog.location:
            html_candidates.append(parse_eagenda_items_from_file(html_doc.catalog.location))

    if not html_candidates:
        return []

    html_candidates = [items for items in html_candidates if items]
    if not html_candidates:
        return []
    return sorted(html_candidates, key=quality_scorer, reverse=True)[0]
