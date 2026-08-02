import pipeline.semantic_backend_runtime as semantic_backend_runtime
from pipeline.semantic_backend_types import SemanticCandidate, SemanticConfigError, SemanticRerankResult
from pipeline.semantic_faiss_backend import FaissSemanticBackend
from pipeline.semantic_pgvector_backend import PgvectorSemanticBackend


def test_backend_selection_faiss(monkeypatch):
    monkeypatch.setattr(semantic_backend_runtime, "SEMANTIC_BACKEND", "faiss")

    backend = semantic_backend_runtime.get_semantic_backend()

    assert isinstance(backend, FaissSemanticBackend)
    assert type(backend) is FaissSemanticBackend


def test_backend_selection_pgvector(monkeypatch):
    monkeypatch.setattr(semantic_backend_runtime, "SEMANTIC_BACKEND", "pgvector")

    backend = semantic_backend_runtime.get_semantic_backend()

    assert isinstance(backend, PgvectorSemanticBackend)
    assert type(backend) is PgvectorSemanticBackend


def test_semantic_contract_types_have_direct_owner():
    candidate = SemanticCandidate(row_id=1, score=0.5, metadata={"catalog_id": 10})
    rerank = SemanticRerankResult(candidates=[candidate], diagnostics={"engine": "pgvector"})

    assert rerank.candidates == [candidate]
    assert issubclass(SemanticConfigError, RuntimeError)
