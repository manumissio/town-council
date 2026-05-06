from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Protocol, TypeAlias

from pipeline.models import Document


AgendaItemRecord: TypeAlias = dict[str, object]
ResolvedAgendaPayload: TypeAlias = dict[str, object]


class AgendaExtractor(Protocol):
    def extract_agenda(self, content: str) -> list[AgendaItemRecord]: ...


class CatalogLike(Protocol):
    location: str | None
    content: str | None


class PlaceLike(Protocol):
    legistar_client: str | None


class EventLike(Protocol):
    record_date: date | None
    place: PlaceLike | None
    documents: Sequence[Document] | None


class DocumentLike(Protocol):
    event_id: int | None
    event: EventLike | None


class AgendaDocumentQuery(Protocol):
    def join(self, *args: object) -> "AgendaDocumentQuery": ...
    def filter(self, *args: object) -> "AgendaDocumentQuery": ...
    def all(self) -> list[Document]: ...


class AgendaResolverSession(Protocol):
    def query(self, model: type[Document]) -> AgendaDocumentQuery: ...


QualityScorer: TypeAlias = Callable[[Sequence[object]], int]
HtmlAgendaLoader: TypeAlias = Callable[
    [AgendaResolverSession, CatalogLike, DocumentLike | None],
    list[AgendaItemRecord],
]
LegistarAgendaFetcher: TypeAlias = Callable[[str | None, date | None], list[AgendaItemRecord]]
LegistarFilter: TypeAlias = Callable[[list[AgendaItemRecord]], list[AgendaItemRecord]]
LegistarAcceptanceChecker: TypeAlias = Callable[[list[AgendaItemRecord]], bool]
PageNumberEnricher: TypeAlias = Callable[
    [list[AgendaItemRecord], list[AgendaItemRecord]],
    list[AgendaItemRecord],
]
