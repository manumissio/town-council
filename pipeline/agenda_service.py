from __future__ import annotations

from importlib import import_module
from typing import Final, Protocol, Sequence, TypedDict

from pipeline.agenda_verification_model_access import (
    AgendaItemRecord,
    AgendaVerificationSession,
    build_agenda_item_record,
    delete_agenda_items_for_catalog,
    load_catalog_for_agenda_hash,
)
from pipeline.summary_freshness import compute_agenda_items_hash


AGENDA_ITEM_ENTITY_TYPE: Final = "agendaitem"


class OcdIdGenerator(Protocol):
    def __call__(self, entity_type: str) -> str: ...


class AgendaItemPayload(TypedDict, total=False):
    order: int | None
    title: str
    description: str | None
    classification: str | None
    result: str | None
    page_number: int | None
    legistar_matter_id: int | None


def _generate_agenda_item_ocd_id() -> str:
    utils_module = import_module("pipeline.utils")
    generate_ocd_id: OcdIdGenerator = utils_module.generate_ocd_id
    return generate_ocd_id(AGENDA_ITEM_ENTITY_TYPE)


def persist_agenda_items(
    session: AgendaVerificationSession,
    catalog_id: int,
    event_id: int,
    items_data: Sequence[AgendaItemPayload] | None,
) -> list[AgendaItemRecord]:
    """
    Replace agenda rows for a catalog and return the newly created agenda items.
    """
    delete_agenda_items_for_catalog(session, catalog_id=catalog_id)

    created_items: list[AgendaItemRecord] = []
    for agenda_item_payload in items_data or ():
        title = agenda_item_payload.get("title")
        if not title:
            continue

        agenda_item = build_agenda_item_record(
            ocd_id=_generate_agenda_item_ocd_id(),
            event_id=event_id,
            catalog_id=catalog_id,
            order=agenda_item_payload.get("order"),
            title=title,
            description=agenda_item_payload.get("description"),
            classification=agenda_item_payload.get("classification"),
            result=agenda_item_payload.get("result"),
            page_number=agenda_item_payload.get("page_number"),
            legistar_matter_id=agenda_item_payload.get("legistar_matter_id"),
        )
        session.add(agenda_item)
        created_items.append(agenda_item)

    catalog = load_catalog_for_agenda_hash(session, catalog_id=catalog_id)
    if catalog is not None:
        catalog.agenda_items_hash = compute_agenda_items_hash(created_items)

    return created_items
