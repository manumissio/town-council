import numpy as np

from pipeline.models import Place, Organization, Event, Catalog, Document, AgendaItem
from pipeline.semantic_index import FaissSemanticBackend


def test_semantic_index_build_uses_summary_then_agenda_fallback(db_session, monkeypatch):
    place = Place(
        id=1,
        name="cupertino",
        display_name="ca_cupertino",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:cupertino",
    )
    org = Organization(id=1, name="City Council", place_id=1)
    db_session.add_all([place, org])

    event_with_summary = Event(id=1, place_id=1, organization_id=1, name="Meeting A")
    event_with_agenda = Event(id=2, place_id=1, organization_id=1, name="Meeting B")
    db_session.add_all([event_with_summary, event_with_agenda])

    cat_summary = Catalog(id=1, url_hash="u1", content="Long content A", summary="Budget vote summary")
    cat_agenda = Catalog(id=2, url_hash="u2", content="Long content B")
    db_session.add_all([cat_summary, cat_agenda])

    doc1 = Document(id=1, place_id=1, event_id=1, catalog_id=1)
    doc2 = Document(id=2, place_id=1, event_id=2, catalog_id=2)
    db_session.add_all([doc1, doc2])

    agenda_item = AgendaItem(
        id=1,
        event_id=2,
        catalog_id=2,
        title="Adopt zoning updates",
        description="Council to consider zoning variance changes.",
    )
    db_session.add(agenda_item)
    db_session.commit()

    backend = FaissSemanticBackend()
    monkeypatch.setattr(backend, "_encode", lambda texts: np.ones((len(texts), 4), dtype=np.float32))

    captured = {}
    monkeypatch.setattr(backend, "_write_artifacts", lambda vectors, rows, meta: captured.update({"rows": rows, "meta": meta}))
    monkeypatch.setattr(backend, "_load_artifacts", lambda: None)

    result = backend.build_index(db_session)
    assert result.row_count >= 2
    assert result.catalog_count == 2
    assert result.source_counts["summary"] >= 1
    assert result.source_counts["agenda_item"] >= 1
    assert isinstance(captured["rows"], list)
    assert captured["meta"]["row_count"] == result.row_count
