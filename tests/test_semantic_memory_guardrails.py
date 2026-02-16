import pytest

from pipeline.semantic_index import FaissSemanticBackend, SemanticConfigError
from pipeline import semantic_index


def test_faiss_guardrail_blocks_multiprocess(monkeypatch):
    backend = FaissSemanticBackend()
    monkeypatch.setattr(semantic_index, "SEMANTIC_REQUIRE_SINGLE_PROCESS", True)
    monkeypatch.setattr(semantic_index, "SEMANTIC_ALLOW_MULTIPROCESS", False)
    monkeypatch.setattr(semantic_index, "_looks_like_multiprocess_worker", lambda: True)
    with pytest.raises(SemanticConfigError):
        backend._guard_runtime()
