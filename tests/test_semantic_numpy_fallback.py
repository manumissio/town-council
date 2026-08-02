import json
from pathlib import Path

import numpy as np

import pipeline.semantic_backend_runtime as semantic_backend_runtime
import pipeline.semantic_faiss_artifacts as semantic_faiss_artifacts
from pipeline.semantic_faiss_backend import FaissSemanticBackend


class _FakeSentenceTransformer:
    def __init__(self, _model_name: str):
        self.model_name = _model_name

    def encode(self, texts: list[str], *, batch_size: int, show_progress_bar: bool) -> np.ndarray:
        assert batch_size == 32
        assert show_progress_bar is False
        return np.repeat(np.array([[1.0, 0.0]], dtype=np.float32), len(texts), axis=0)


def _write_numpy_artifacts(index_dir: Path, vectors: np.ndarray, rows: list[dict[str, object]]) -> None:
    np.save(index_dir / "semantic_index.npy", vectors)
    (index_dir / "semantic_ids.json").write_text(json.dumps(rows), encoding="utf-8")
    (index_dir / "semantic_meta.json").write_text(
        json.dumps({"model_name": "test", "engine": "numpy"}),
        encoding="utf-8",
    )


def test_faiss_backend_uses_numpy_fallback_when_faiss_missing(monkeypatch, tmp_path, reset_faiss_semantic_backend):
    monkeypatch.setattr(semantic_backend_runtime, "faiss", None)
    monkeypatch.setattr(semantic_backend_runtime, "SentenceTransformer", _FakeSentenceTransformer)
    monkeypatch.setattr(semantic_faiss_artifacts, "SEMANTIC_INDEX_DIR", str(tmp_path))
    backend = FaissSemanticBackend()

    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    rows = [
        {"row_id": 0, "result_type": "meeting", "catalog_id": 10, "db_id": 10},
        {"row_id": 1, "result_type": "meeting", "catalog_id": 20, "db_id": 20},
    ]
    _write_numpy_artifacts(tmp_path, vectors, rows)

    hits = backend.query("budget", 2)

    assert len(hits) == 2
    assert hits[0].metadata["catalog_id"] == 10
