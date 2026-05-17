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


def test_faiss_health_hides_exception_detail(monkeypatch):
    semantic_index.FaissSemanticBackend._instance = None
    backend = FaissSemanticBackend()
    monkeypatch.setattr(backend, "_guard_runtime", lambda: None)
    monkeypatch.setattr(backend, "_load_artifacts", lambda: (_ for _ in ()).throw(FileNotFoundError("/secret/index.faiss")))

    health = backend.health()

    assert health == {"status": "error", "error": "FileNotFoundError"}
