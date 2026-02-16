from pipeline import semantic_index


def test_backend_selection_faiss(monkeypatch):
    monkeypatch.setattr(semantic_index, "SEMANTIC_BACKEND", "faiss")
    backend = semantic_index.get_semantic_backend()
    assert isinstance(backend, semantic_index.FaissSemanticBackend)


def test_backend_selection_pgvector(monkeypatch):
    monkeypatch.setattr(semantic_index, "SEMANTIC_BACKEND", "pgvector")
    backend = semantic_index.get_semantic_backend()
    assert isinstance(backend, semantic_index.PgvectorSemanticBackend)
