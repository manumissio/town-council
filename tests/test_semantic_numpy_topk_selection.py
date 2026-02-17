import numpy as np

from pipeline import semantic_index


def _build_backend_with_numpy_artifacts(monkeypatch, tmp_path, vectors, rows, query_vec):
    monkeypatch.setattr(semantic_index, "faiss", None)
    monkeypatch.setattr(semantic_index, "SEMANTIC_INDEX_DIR", str(tmp_path))
    semantic_index.FaissSemanticBackend._instance = None
    backend = semantic_index.FaissSemanticBackend()

    backend._write_artifacts(vectors, rows, {"model_name": "test"})
    backend._index = None
    backend._matrix = None
    backend._metadata = []
    backend._meta = {}
    monkeypatch.setattr(backend, "_encode", lambda texts: np.asarray([query_vec], dtype=np.float32))
    return backend


def test_numpy_topk_selection_k1(monkeypatch, tmp_path):
    vectors = np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]], dtype=np.float32)
    rows = [
        {"row_id": 0, "result_type": "meeting", "catalog_id": 10, "db_id": 10},
        {"row_id": 1, "result_type": "meeting", "catalog_id": 20, "db_id": 20},
        {"row_id": 2, "result_type": "meeting", "catalog_id": 30, "db_id": 30},
    ]
    backend = _build_backend_with_numpy_artifacts(monkeypatch, tmp_path, vectors, rows, query_vec=[1.0, 0.0])

    hits = backend.query("budget", 1)
    assert len(hits) == 1
    assert hits[0].metadata["catalog_id"] == 10


def test_numpy_topk_selection_k_equals_n(monkeypatch, tmp_path):
    vectors = np.array([[1.0, 0.0], [0.6, 0.4], [0.0, 1.0]], dtype=np.float32)
    rows = [
        {"row_id": 0, "result_type": "meeting", "catalog_id": 10, "db_id": 10},
        {"row_id": 1, "result_type": "meeting", "catalog_id": 20, "db_id": 20},
        {"row_id": 2, "result_type": "meeting", "catalog_id": 30, "db_id": 30},
    ]
    backend = _build_backend_with_numpy_artifacts(monkeypatch, tmp_path, vectors, rows, query_vec=[1.0, 0.0])

    hits = backend.query("budget", 3)
    assert len(hits) == 3
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_numpy_topk_selection_handles_duplicate_scores(monkeypatch, tmp_path):
    vectors = np.array([[1.0, 0.0], [1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype=np.float32)
    rows = [
        {"row_id": 0, "result_type": "meeting", "catalog_id": 10, "db_id": 10},
        {"row_id": 1, "result_type": "meeting", "catalog_id": 20, "db_id": 20},
        {"row_id": 2, "result_type": "meeting", "catalog_id": 30, "db_id": 30},
        {"row_id": 3, "result_type": "meeting", "catalog_id": 40, "db_id": 40},
    ]
    backend = _build_backend_with_numpy_artifacts(monkeypatch, tmp_path, vectors, rows, query_vec=[1.0, 0.0])

    hits = backend.query("budget", 2)
    assert len(hits) == 2
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    returned_ids = {h.metadata["catalog_id"] for h in hits}
    assert returned_ids.issubset({10, 20, 30})
