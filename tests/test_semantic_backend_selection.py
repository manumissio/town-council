from pipeline import semantic_index
from pipeline import semantic_backend_types, semantic_faiss_backend, semantic_pgvector_backend


def test_backend_selection_faiss(monkeypatch):
    monkeypatch.setattr(semantic_index, "SEMANTIC_BACKEND", "faiss")
    backend = semantic_index.get_semantic_backend()
    assert isinstance(backend, semantic_index.FaissSemanticBackend)
    assert type(backend) is semantic_index.FaissSemanticBackend
    assert semantic_index.FaissSemanticBackend is semantic_faiss_backend.FaissSemanticBackend


def test_backend_selection_pgvector(monkeypatch):
    monkeypatch.setattr(semantic_index, "SEMANTIC_BACKEND", "pgvector")
    backend = semantic_index.get_semantic_backend()
    assert isinstance(backend, semantic_index.PgvectorSemanticBackend)
    assert type(backend) is semantic_index.PgvectorSemanticBackend
    assert semantic_index.PgvectorSemanticBackend is semantic_pgvector_backend.PgvectorSemanticBackend


def test_semantic_index_reexports_backend_contract_types():
    assert semantic_index.SemanticCandidate is semantic_backend_types.SemanticCandidate
    assert semantic_index.SemanticRerankResult is semantic_backend_types.SemanticRerankResult
    assert semantic_index.SemanticConfigError is semantic_backend_types.SemanticConfigError
