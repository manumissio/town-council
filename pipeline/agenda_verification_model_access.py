from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, NamedTuple, Protocol

from sqlalchemy.engine import Connection, Engine


class AgendaCatalogRecord(Protocol):
    agenda_items_hash: str | None
    location: str | None


class AgendaItemRecord(Protocol):
    id: int | None
    catalog_id: int | None
    order: int | None
    title: str | None
    description: str | None
    classification: str | None
    result: str | None
    page_number: int | None
    spatial_coords: list[dict[str, object]] | None
    votes: dict[str, object] | None
    raw_history: str | None


class AgendaItemFactory(Protocol):
    catalog_id: Any
    raw_history: Any
    spatial_coords: Any

    def __call__(
        self,
        *,
        ocd_id: str,
        event_id: int,
        catalog_id: int,
        order: int | None,
        title: str,
        description: str | None,
        classification: str | None,
        result: str | None,
        page_number: int | None,
        legistar_matter_id: int | None,
    ) -> AgendaItemRecord: ...


class CatalogFactory(Protocol):
    id: Any


class AgendaVerificationQuery(Protocol):
    def filter(self, *criteria: object) -> AgendaVerificationQuery: ...

    def filter_by(self, **kwargs: object) -> AgendaVerificationQuery: ...

    def all(self) -> list[AgendaItemRecord]: ...

    def delete(self) -> int: ...


class AgendaVerificationSession(Protocol):
    def query(self, *entities: object, **kwargs: object) -> AgendaVerificationQuery: ...

    def add(self, instance: object) -> None: ...

    def get(self, entity: object, ident: object, **kwargs: object) -> AgendaCatalogRecord | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class AgendaVerificationModels(NamedTuple):
    db_connect: Callable[[], Engine | Connection]
    agenda_item: AgendaItemFactory
    catalog: CatalogFactory


def _load_agenda_verification_models() -> AgendaVerificationModels:
    # Runtime-loaded ORM symbols keep typed services from inheriting the entire
    # untyped SQLAlchemy model surface.
    models_module = import_module("pipeline.models")
    return AgendaVerificationModels(
        db_connect=models_module.db_connect,
        agenda_item=models_module.AgendaItem,
        catalog=models_module.Catalog,
    )


def delete_agenda_items_for_catalog(db_session: AgendaVerificationSession, *, catalog_id: int) -> None:
    models = _load_agenda_verification_models()
    db_session.query(models.agenda_item).filter_by(catalog_id=catalog_id).delete()


def build_agenda_item_record(
    *,
    ocd_id: str,
    event_id: int,
    catalog_id: int,
    order: int | None,
    title: str,
    description: str | None,
    classification: str | None,
    result: str | None,
    page_number: int | None,
    legistar_matter_id: int | None,
) -> AgendaItemRecord:
    models = _load_agenda_verification_models()
    return models.agenda_item(
        ocd_id=ocd_id,
        event_id=event_id,
        catalog_id=catalog_id,
        order=order,
        title=title,
        description=description,
        classification=classification,
        result=result,
        page_number=page_number,
        legistar_matter_id=legistar_matter_id,
    )


def load_catalog_for_agenda_hash(
    db_session: AgendaVerificationSession,
    *,
    catalog_id: int,
) -> AgendaCatalogRecord | None:
    models = _load_agenda_verification_models()
    catalog: AgendaCatalogRecord | None = db_session.get(models.catalog, catalog_id)
    return catalog


def open_verification_session() -> AgendaVerificationSession:
    models = _load_agenda_verification_models()
    sqlalchemy_orm_module = import_module("sqlalchemy.orm")
    session_factory = sqlalchemy_orm_module.sessionmaker(bind=models.db_connect())
    verification_session: AgendaVerificationSession = session_factory()
    return verification_session


def select_pending_verification_items(db_session: AgendaVerificationSession) -> list[AgendaItemRecord]:
    models = _load_agenda_verification_models()
    pending_items: list[AgendaItemRecord] = (
        db_session.query(models.agenda_item)
        .filter(
            models.agenda_item.raw_history != None,  # noqa: E711 - SQLAlchemy null comparison
            models.agenda_item.spatial_coords == None,  # noqa: E711 - SQLAlchemy null comparison
        )
        .all()
    )
    return pending_items


def load_catalog_for_verification(
    db_session: AgendaVerificationSession,
    *,
    catalog_id: int | None,
) -> AgendaCatalogRecord | None:
    if catalog_id is None:
        return None
    return load_catalog_for_agenda_hash(db_session, catalog_id=catalog_id)
