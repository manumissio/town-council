import pytest

import pipeline.semantic_backend_runtime as semantic_backend_runtime
import pipeline.semantic_faiss_artifacts as semantic_faiss_artifacts
import pipeline.semantic_faiss_backend as semantic_faiss_backend
from pipeline.semantic_backend_types import SemanticConfigError
from pipeline.semantic_faiss_backend import FaissSemanticBackend


def test_semantic_require_faiss_raises_when_faiss_missing(monkeypatch, reset_faiss_semantic_backend):
    backend = FaissSemanticBackend()
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_REQUIRE_FAISS", True)
    monkeypatch.setattr(semantic_backend_runtime, "faiss", None)
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_REQUIRE_SINGLE_PROCESS", False)
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_ALLOW_MULTIPROCESS", True)

    with pytest.raises(SemanticConfigError):
        backend.health()


def test_faiss_health_hides_exception_detail(monkeypatch, reset_faiss_semantic_backend, tmp_path):
    backend = FaissSemanticBackend()
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_REQUIRE_FAISS", False)
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_REQUIRE_SINGLE_PROCESS", False)
    monkeypatch.setattr(semantic_faiss_backend, "SEMANTIC_ALLOW_MULTIPROCESS", True)
    monkeypatch.setattr(semantic_backend_runtime, "faiss", None)
    monkeypatch.setattr(semantic_faiss_artifacts, "SEMANTIC_INDEX_DIR", str(tmp_path))

    health = backend.health()

    assert health == {"status": "error", "error": "FileNotFoundError"}
