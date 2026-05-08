from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from typing import Any

import numpy as np

from pipeline.semantic_backend_types import BuildResult, SemanticBackend, SemanticCandidate, SemanticConfigError
from pipeline.semantic_faiss_artifacts import _artifact_paths, _load_artifacts, _write_artifacts
from pipeline.semantic_faiss_rows import _collect_rows
from pipeline.semantic_text import _safe_text


def _semantic_index_facade():
    from pipeline import semantic_index

    return semantic_index


class FaissSemanticBackend(SemanticBackend):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FaissSemanticBackend, cls).__new__(cls)
                    cls._instance._model = None
                    cls._instance._index = None
                    cls._instance._matrix = None
                    cls._instance._metadata = []
                    cls._instance._meta = {}
        return cls._instance

    def _guard_runtime(self) -> None:
        semantic_index = _semantic_index_facade()
        if not semantic_index.SEMANTIC_ALLOW_MULTIPROCESS:
            if semantic_index.SEMANTIC_REQUIRE_SINGLE_PROCESS and semantic_index._looks_like_multiprocess_worker():
                raise SemanticConfigError(
                    "Unsafe semantic backend configuration detected (multiprocess runtime). "
                    "Use a single worker/process for FAISS mode or set SEMANTIC_ALLOW_MULTIPROCESS=true explicitly."
                )
        if semantic_index.SEMANTIC_REQUIRE_FAISS and semantic_index.faiss is None:
            raise SemanticConfigError(
                "SEMANTIC_REQUIRE_FAISS=true but faiss-cpu is unavailable in this runtime. "
                "Install/repair faiss-cpu or set SEMANTIC_REQUIRE_FAISS=false to allow numpy fallback."
            )

    def _ensure_model(self):
        self._guard_runtime()
        if self._model is not None:
            return self._model
        semantic_index = _semantic_index_facade()
        if semantic_index.SentenceTransformer is None:
            raise SemanticConfigError("sentence-transformers is not installed in this environment.")
        with self._lock:
            if self._model is None:
                self._model = semantic_index.SentenceTransformer(semantic_index.SEMANTIC_MODEL_NAME)
        return self._model

    def _encode(self, texts: list[str]) -> np.ndarray:
        model = self._ensure_model()
        vectors = model.encode(texts, batch_size=32, show_progress_bar=False)
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        faiss_backend = _semantic_index_facade().faiss
        if faiss_backend is not None:
            faiss_backend.normalize_L2(arr)
        return arr

    _artifact_paths = _artifact_paths
    _load_artifacts = _load_artifacts
    _write_artifacts = _write_artifacts
    _collect_rows = _collect_rows

    def build_index(self, db) -> BuildResult:
        semantic_index = _semantic_index_facade()
        texts, rows, source_counts = self._collect_rows(db)
        if not texts:
            raise SemanticConfigError("No semantic rows available to index.")

        vectors = self._encode(texts)
        source_payload = json.dumps(rows, sort_keys=True).encode("utf-8")
        corpus_hash = hashlib.sha256(source_payload).hexdigest()
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        build_meta = {
            "model_name": semantic_index.SEMANTIC_MODEL_NAME,
            "built_at": now_iso,
            "row_count": len(rows),
            "catalog_count": len({r["catalog_id"] for r in rows}),
            "corpus_hash": corpus_hash,
            "source_counts": source_counts,
        }
        self._write_artifacts(vectors, rows, build_meta)

        with self._lock:
            self._index = None
            self._matrix = None
            self._metadata = []
            self._meta = {}
        self._load_artifacts()

        return BuildResult(
            row_count=build_meta["row_count"],
            catalog_count=build_meta["catalog_count"],
            source_counts=source_counts,
            corpus_hash=corpus_hash,
            model_name=semantic_index.SEMANTIC_MODEL_NAME,
            built_at=now_iso,
        )

    def query(self, query_text: str, top_k: int) -> list[SemanticCandidate]:
        self._load_artifacts()
        if not self._metadata or self._index is None:
            return []

        query = _safe_text(query_text)
        if not query:
            return []
        query_vec = self._encode([query])
        k = max(1, min(int(top_k), len(self._metadata)))
        scores, indices = self._search_vectors(query_vec, k)
        return self._semantic_candidates(scores, indices)

    def _search_vectors(self, query_vec: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        faiss_backend = _semantic_index_facade().faiss
        if faiss_backend is not None and hasattr(self._index, "search"):
            return self._index.search(query_vec, k)
        matrix = self._matrix if self._matrix is not None else np.asarray(self._index, dtype=np.float32)
        sims = np.dot(matrix, query_vec[0])
        if k >= sims.shape[0]:
            top_idx = np.argsort(-sims)
        else:
            top_idx = np.argpartition(-sims, k - 1)[:k]
            top_idx = top_idx[np.argsort(-sims[top_idx])]
        return np.array([sims[top_idx]], dtype=np.float32), np.array([top_idx], dtype=np.int64)

    def _semantic_candidates(self, scores: np.ndarray, indices: np.ndarray) -> list[SemanticCandidate]:
        semantic_candidates: list[SemanticCandidate] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            row = self._metadata[idx]
            semantic_candidates.append(
                SemanticCandidate(row_id=int(row.get("row_id", idx)), score=float(score), metadata=row)
            )
        return semantic_candidates

    def health(self) -> dict[str, Any]:
        self._guard_runtime()
        try:
            self._load_artifacts()
            paths = self._artifact_paths()
            engine = self._meta.get("engine")
            if not engine:
                engine = "faiss" if _semantic_index_facade().faiss is not None else "numpy"
            return {
                "status": "ok",
                "row_count": len(self._metadata),
                "model_name": self._meta.get("model_name"),
                "built_at": self._meta.get("built_at"),
                "engine": engine,
                "artifacts": {
                    "faiss": paths["faiss"].exists(),
                    "npy": paths["npy"].exists(),
                    "ids": paths["ids"].exists(),
                    "meta": paths["meta"].exists(),
                },
            }
        except (FileNotFoundError, json.JSONDecodeError, OSError, RuntimeError, ValueError) as exc:
            return {"status": "error", "error": exc.__class__.__name__, "detail": str(exc)}
