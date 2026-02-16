import pytest

from pipeline import semantic_index
from pipeline.semantic_index import FaissSemanticBackend, SemanticConfigError


def test_semantic_require_faiss_raises_when_faiss_missing(monkeypatch):
    semantic_index.FaissSemanticBackend._instance = None
    backend = FaissSemanticBackend()
    monkeypatch.setattr(semantic_index, "SEMANTIC_REQUIRE_FAISS", True)
    monkeypatch.setattr(semantic_index, "faiss", None)
    monkeypatch.setattr(semantic_index, "SEMANTIC_REQUIRE_SINGLE_PROCESS", False)
    monkeypatch.setattr(semantic_index, "SEMANTIC_ALLOW_MULTIPROCESS", True)
    with pytest.raises(SemanticConfigError):
        backend._guard_runtime()
