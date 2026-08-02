import json
from functools import partial
from pathlib import Path

import numpy as np

import pipeline.semantic_backend_runtime as semantic_backend_runtime
import pipeline.semantic_faiss_artifacts as semantic_faiss_artifacts
from pipeline.semantic_faiss_backend import FaissSemanticBackend


class _FakeSentenceTransformer:
    def __init__(self, _model_name: str, *, query_vector: np.ndarray):
        self.query_vector = query_vector

    def encode(self, texts: list[str], *, batch_size: int, show_progress_bar: bool) -> np.ndarray:
        assert batch_size == 32
        assert show_progress_bar is False
        return np.repeat(self.query_vector.reshape(1, -1), len(texts), axis=0)


def _write_numpy_artifacts(index_dir: Path, vectors: np.ndarray, rows: list[dict[str, object]]) -> None:
    np.save(index_dir / "semantic_index.npy", vectors)
    (index_dir / "semantic_ids.json").write_text(json.dumps(rows), encoding="utf-8")
    (index_dir / "semantic_meta.json").write_text(
        json.dumps({"model_name": "test", "engine": "numpy"}),
        encoding="utf-8",
    )


def _build_backend_with_numpy_artifacts(monkeypatch, tmp_path, vectors, rows, query_vec):
    query_vector = np.asarray(query_vec, dtype=np.float32)
    fake_transformer = partial(_FakeSentenceTransformer, query_vector=query_vector)
    monkeypatch.setattr(semantic_backend_runtime, "faiss", None)
    monkeypatch.setattr(semantic_backend_runtime, "SentenceTransformer", fake_transformer)
    monkeypatch.setattr(semantic_faiss_artifacts, "SEMANTIC_INDEX_DIR", str(tmp_path))
    _write_numpy_artifacts(tmp_path, vectors, rows)
    return FaissSemanticBackend()


def test_numpy_topk_selection_k1(monkeypatch, tmp_path, reset_faiss_semantic_backend):
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


def test_numpy_topk_selection_k_equals_n(monkeypatch, tmp_path, reset_faiss_semantic_backend):
    vectors = np.array([[1.0, 0.0], [0.6, 0.4], [0.0, 1.0]], dtype=np.float32)
    rows = [
        {"row_id": 0, "result_type": "meeting", "catalog_id": 10, "db_id": 10},
        {"row_id": 1, "result_type": "meeting", "catalog_id": 20, "db_id": 20},
        {"row_id": 2, "result_type": "meeting", "catalog_id": 30, "db_id": 30},
    ]
    backend = _build_backend_with_numpy_artifacts(monkeypatch, tmp_path, vectors, rows, query_vec=[1.0, 0.0])

    hits = backend.query("budget", 3)

    assert len(hits) == 3
    scores = [hit.score for hit in hits]
    assert scores == sorted(scores, reverse=True)


def test_numpy_topk_selection_handles_duplicate_scores(monkeypatch, tmp_path, reset_faiss_semantic_backend):
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
    scores = [hit.score for hit in hits]
    assert scores == sorted(scores, reverse=True)
    returned_ids = {hit.metadata["catalog_id"] for hit in hits}
    assert returned_ids.issubset({10, 20, 30})
