import json

import numpy as np

import pipeline.semantic_backend_runtime as semantic_backend_runtime
import pipeline.semantic_faiss_artifacts as semantic_faiss_artifacts
import pipeline.semantic_faiss_backend as semantic_faiss_backend
from pipeline.models import Place, Organization, Event, Catalog, Document, AgendaItem
from pipeline.semantic_faiss_backend import FaissSemanticBackend


class _FakeSentenceTransformer:
    def __init__(self, _model_name: str):
        self.model_name = _model_name

    def encode(self, texts: list[str], *, batch_size: int, show_progress_bar: bool) -> np.ndarray:
        assert batch_size == 32
        assert show_progress_bar is False
        return np.ones((len(texts), 4), dtype=np.float32)


def _configure_numpy_build(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(semantic_backend_runtime, "faiss", None)
    monkeypatch.setattr(semantic_backend_runtime, "SentenceTransformer", _FakeSentenceTransformer)
    monkeypatch.setattr(semantic_faiss_artifacts, "SEMANTIC_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_MODEL_NAME", "test-model")


def test_semantic_index_build_uses_summary_then_agenda_fallback(
    db_session, monkeypatch, tmp_path, reset_faiss_semantic_backend
):
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

    _configure_numpy_build(monkeypatch, tmp_path)
    backend = FaissSemanticBackend()

    result = backend.build_index(db_session)

    rows = json.loads((tmp_path / "semantic_ids.json").read_text(encoding="utf-8"))
    metadata = json.loads((tmp_path / "semantic_meta.json").read_text(encoding="utf-8"))
    assert result.row_count >= 2
    assert result.catalog_count == 2
    assert result.source_counts["summary"] >= 1
    assert result.source_counts["agenda_item"] >= 1
    assert isinstance(rows, list)
    assert metadata["row_count"] == result.row_count
    assert (tmp_path / "semantic_index.npy").exists()


def test_semantic_index_build_uses_agenda_items_when_catalog_text_is_empty(
    db_session, monkeypatch, tmp_path, reset_faiss_semantic_backend
):
    place = Place(
        id=11,
        name="berkeley",
        display_name="ca_berkeley",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:berkeley",
    )
    org = Organization(id=11, name="City Council", place_id=11)
    event = Event(id=11, place_id=11, organization_id=11, name="Meeting C")
    catalog = Catalog(id=11, url_hash="u11", content=None, summary=None, summary_extractive=None)
    document = Document(id=11, place_id=11, event_id=11, catalog_id=11)
    agenda_item = AgendaItem(
        id=11,
        event_id=11,
        catalog_id=11,
        title="Adopt climate action ordinance",
        description="Council will consider adoption language and implementation milestones.",
    )
    db_session.add_all([place, org, event, catalog, document, agenda_item])
    db_session.commit()

    _configure_numpy_build(monkeypatch, tmp_path)
    backend = FaissSemanticBackend()

    result = backend.build_index(db_session)

    assert result.row_count >= 1
    assert result.source_counts["agenda_item"] >= 1
    assert (tmp_path / "semantic_index.npy").exists()
