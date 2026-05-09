from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any

import numpy as np

from pipeline.models import SemanticEmbedding
from pipeline.semantic_backend_types import BuildResult, SemanticBackend, SemanticCandidate, SemanticConfigError
from pipeline.semantic_pgvector_rerank import rerank_candidates_with_diagnostics
from pipeline.semantic_pgvector_rows import _collect_catalog_summary_rows

logger = logging.getLogger("semantic-index")


def _semantic_index_facade():
    from pipeline import semantic_index

    return semantic_index


class PgvectorSemanticBackend(SemanticBackend):
    _model = None
    _lock = threading.Lock()
    _collect_catalog_summary_rows = _collect_catalog_summary_rows
    rerank_candidates_with_diagnostics = rerank_candidates_with_diagnostics

    def _ensure_model(self):
        semantic_index = _semantic_index_facade()
        if semantic_index.SentenceTransformer is None:
            raise SemanticConfigError("sentence-transformers is not installed in this environment.")
        if self._model is not None:
            return self._model
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
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    @staticmethod
    def _vector_literal(vector: np.ndarray) -> str:
        return "[" + ",".join(f"{float(v):.8f}" for v in vector.tolist()) + "]"

    def build_index(self, db) -> BuildResult:
        semantic_index = _semantic_index_facade()
        rows = self._collect_catalog_summary_rows(db)
        if not rows:
            raise SemanticConfigError("No catalog summaries available to embed for pgvector.")

        embeddings = self._encode([row["text"] for row in rows])
        existing_by_catalog = self._existing_embeddings_by_catalog(db, [int(row["catalog_id"]) for row in rows])

        changed = 0
        for row, vec in zip(rows, embeddings):
            if self._upsert_embedding(db, existing_by_catalog, row, vec, semantic_index.SEMANTIC_MODEL_NAME):
                changed += 1
        db.commit()

        corpus_hash = self._corpus_hash(rows)
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        source_counts = {"summary": len(rows), "agenda_item": 0, "content_chunk": 0, "agenda_item_result": 0}
        logger.info(
            "pgvector_reindex_complete rows=%s changed=%s model=%s",
            len(rows),
            changed,
            semantic_index.SEMANTIC_MODEL_NAME,
        )
        return BuildResult(
            row_count=len(rows),
            catalog_count=len({int(row["catalog_id"]) for row in rows}),
            source_counts=source_counts,
            corpus_hash=corpus_hash,
            model_name=semantic_index.SEMANTIC_MODEL_NAME,
            built_at=now_iso,
        )

    def _existing_embeddings_by_catalog(self, db, catalog_ids: list[int]) -> dict[int, SemanticEmbedding]:
        semantic_index = _semantic_index_facade()
        existing = (
            db.query(SemanticEmbedding)
            .filter(
                SemanticEmbedding.catalog_id.in_(catalog_ids),
                SemanticEmbedding.model_name == semantic_index.SEMANTIC_MODEL_NAME,
            )
            .all()
        )
        return {int(embedding.catalog_id): embedding for embedding in existing if embedding.catalog_id is not None}

    def _upsert_embedding(
        self,
        db,
        existing_by_catalog: dict[int, SemanticEmbedding],
        row: dict[str, Any],
        vec: np.ndarray,
        model_name: str,
    ) -> bool:
        catalog_id = int(row["catalog_id"])
        source_hash = row["source_hash"]
        rec = existing_by_catalog.get(catalog_id)
        if rec and rec.source_hash == source_hash:
            return False
        if rec is None:
            rec = SemanticEmbedding(catalog_id=catalog_id, model_name=model_name, embedding_dim=int(vec.shape[0]))
            db.add(rec)
        rec.embedding = vec.tolist()
        rec.embedding_dim = int(vec.shape[0])
        rec.source_hash = source_hash
        return True

    @staticmethod
    def _corpus_hash(rows: list[dict[str, Any]]) -> str:
        payload = json.dumps(
            [{"catalog_id": row["catalog_id"], "source_hash": row["source_hash"]} for row in rows], sort_keys=True
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def query(self, query_text: str, top_k: int) -> list[SemanticCandidate]:
        raise SemanticConfigError(
            "pgvector backend requires hybrid rerank with lexical candidates. "
            "Use /search with semantic=true or /search/semantic."
        )

    def rerank_candidates(self, db, query_text: str, lexical_hits: list[dict], top_k: int) -> list[SemanticCandidate]:
        return self.rerank_candidates_with_diagnostics(db, query_text, lexical_hits, top_k).candidates

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "engine": "pgvector", "model_name": _semantic_index_facade().SEMANTIC_MODEL_NAME}
