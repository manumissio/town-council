import numpy as np

from pipeline import semantic_index


def test_faiss_backend_uses_numpy_fallback_when_faiss_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(semantic_index, "faiss", None)
    monkeypatch.setattr(semantic_index, "SEMANTIC_INDEX_DIR", str(tmp_path))
    semantic_index.FaissSemanticBackend._instance = None
    backend = semantic_index.FaissSemanticBackend()

    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    rows = [
        {"row_id": 0, "result_type": "meeting", "catalog_id": 10, "db_id": 10},
        {"row_id": 1, "result_type": "meeting", "catalog_id": 20, "db_id": 20},
    ]
    backend._write_artifacts(vectors, rows, {"model_name": "test"})

    # Force load from disk to exercise artifact reader logic.
    backend._index = None
    backend._matrix = None
    backend._metadata = []
    backend._meta = {}
    monkeypatch.setattr(backend, "_encode", lambda texts: np.array([[1.0, 0.0]], dtype=np.float32))

    hits = backend.query("budget", 2)
    assert len(hits) == 2
    assert hits[0].metadata["catalog_id"] == 10
