from typing import Dict, List

from pipeline.models import AgendaItem, Catalog
from pipeline.summary_freshness import compute_agenda_items_hash
from pipeline.utils import generate_ocd_id


def persist_agenda_items(session, catalog_id: int, event_id: int, items_data: List[Dict]) -> List[AgendaItem]:
    """
    Replace agenda rows for a catalog and return newly created ORM items.
    """
    session.query(AgendaItem).filter_by(catalog_id=catalog_id).delete()

    created = []
    for data in items_data or []:
        if not data.get("title"):
            continue

        item = AgendaItem(
            ocd_id=generate_ocd_id("agendaitem"),
            event_id=event_id,
            catalog_id=catalog_id,
            order=data.get("order"),
            title=data.get("title", "Untitled"),
            description=data.get("description"),
            classification=data.get("classification"),
            result=data.get("result"),
            page_number=data.get("page_number"),
            legistar_matter_id=data.get("legistar_matter_id"),
        )
        session.add(item)
        created.append(item)

    catalog = session.get(Catalog, catalog_id)
    if catalog is not None:
        catalog.agenda_items_hash = compute_agenda_items_hash(created)

    return created
