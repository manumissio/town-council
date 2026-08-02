import pytest

import pipeline.semantic_faiss_backend as semantic_faiss_backend
from pipeline.semantic_backend_types import SemanticConfigError
from pipeline.semantic_faiss_backend import FaissSemanticBackend


def test_faiss_guardrail_blocks_multiprocess(monkeypatch, reset_faiss_semantic_backend):
    backend = FaissSemanticBackend()
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_REQUIRE_SINGLE_PROCESS", True)
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_ALLOW_MULTIPROCESS", False)
    monkeypatch.setenv("WORKER_CONCURRENCY", "2")

    with pytest.raises(SemanticConfigError):
        backend.health()
