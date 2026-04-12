from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import bindparam, text

from pipeline.models import Catalog, Document, Event, Organization, Place, SemanticEmbedding
from pipeline.semantic_backend_types import BuildResult, SemanticBackend, SemanticCandidate, SemanticConfigError, SemanticRerankResult
from pipeline.semantic_text import _safe_text, catalog_semantic_source_hash, catalog_semantic_text

logger = logging.getLogger("semantic-index")


def _semantic_index_facade():
    from pipeline import semantic_index

    return semantic_index


class PgvectorSemanticBackend(SemanticBackend):
    _model = None
    _lock = threading.Lock()

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

    def _collect_catalog_summary_rows(self, db) -> list[dict[str, Any]]:
        rows = (
            db.query(Document, Catalog, Event, Place, Organization)
            .join(Catalog, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .join(Place, Document.place_id == Place.id)
            .outerjoin(Organization, Event.organization_id == Organization.id)
            .filter(Catalog.summary.isnot(None))
            .all()
        )
        catalog_summary_rows: list[dict[str, Any]] = []
        seen_catalogs: set[int] = set()
        for doc, catalog, event, place, org in rows:
            if catalog.id in seen_catalogs:
                continue
            seen_catalogs.add(catalog.id)
            summary = catalog_semantic_text(catalog.summary)
            source_hash = catalog_semantic_source_hash(catalog.summary)
            if source_hash is None:
                continue
            catalog_summary_rows.append(
                {
                    "catalog_id": catalog.id,
                    "doc_id": doc.id,
                    "event_id": event.id,
                    "city": (place.display_name or place.name or "").lower(),
                    "meeting_category": (event.meeting_type or "Other"),
                    "organization": org.name if org else "City Council",
                    "date": event.record_date.isoformat() if event.record_date else None,
                    "text": summary,
                    "source_hash": source_hash,
                }
            )
        return catalog_summary_rows

    def build_index(self, db) -> BuildResult:
        semantic_index = _semantic_index_facade()
        rows = self._collect_catalog_summary_rows(db)
        if not rows:
            raise SemanticConfigError("No catalog summaries available to embed for pgvector.")

        embeddings = self._encode([row["text"] for row in rows])
        catalog_ids = [int(r["catalog_id"]) for r in rows]
        existing = (
            db.query(SemanticEmbedding)
            .filter(
                SemanticEmbedding.catalog_id.in_(catalog_ids),
                SemanticEmbedding.model_name == semantic_index.SEMANTIC_MODEL_NAME,
            )
            .all()
        )
        existing_by_catalog = {int(e.catalog_id): e for e in existing if e.catalog_id is not None}

        changed = 0
        for row, vec in zip(rows, embeddings):
            catalog_id = int(row["catalog_id"])
            source_hash = row["source_hash"]
            rec = existing_by_catalog.get(catalog_id)
            if rec and rec.source_hash == source_hash:
                continue
            if rec is None:
                rec = SemanticEmbedding(
                    catalog_id=catalog_id,
                    model_name=semantic_index.SEMANTIC_MODEL_NAME,
                    embedding_dim=int(vec.shape[0]),
                )
                db.add(rec)
            rec.embedding = vec.tolist()
            rec.embedding_dim = int(vec.shape[0])
            rec.source_hash = source_hash
            changed += 1
        db.commit()

        source_payload = json.dumps(
            [{"catalog_id": r["catalog_id"], "source_hash": r["source_hash"]} for r in rows], sort_keys=True
        ).encode("utf-8")
        corpus_hash = hashlib.sha256(source_payload).hexdigest()
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
            catalog_count=len({int(r["catalog_id"]) for r in rows}),
            source_counts=source_counts,
            corpus_hash=corpus_hash,
            model_name=semantic_index.SEMANTIC_MODEL_NAME,
            built_at=now_iso,
        )

    def query(self, query_text: str, top_k: int) -> list[SemanticCandidate]:
        raise SemanticConfigError(
            "pgvector backend requires hybrid rerank with lexical candidates. "
            "Use /search with semantic=true or /search/semantic."
        )

    def rerank_candidates_with_diagnostics(
        self,
        db,
        query_text: str,
        lexical_hits: list[dict],
        top_k: int,
    ) -> SemanticRerankResult:
        """
        Hybrid stage-2 rerank: score only lexical meeting candidates via pgvector and
        report whether we had enough fresh embeddings to make semantic mode meaningful.
        """
        semantic_index = _semantic_index_facade()
        diagnostics: dict[str, Any] = {
            "retrieval_mode": "hybrid_pgvector",
            "result_scope": "meeting_hybrid",
            "hybrid_rerank_applied": False,
            "degraded_to_lexical": False,
            "skipped_reason": None,
            "lexical_candidates": len(lexical_hits),
            "eligible_meeting_candidates": 0,
            "candidate_limit_applied": 0,
            "fresh_embeddings": 0,
            "missing_embeddings": 0,
            "stale_embeddings": 0,
            "lexical_fallback_candidates": 0,
        }
        if not lexical_hits:
            diagnostics["skipped_reason"] = "no_lexical_candidates"
            return SemanticRerankResult(candidates=[], diagnostics=diagnostics)

        q = _safe_text(query_text)
        if not q:
            diagnostics["skipped_reason"] = "empty_query"
            return SemanticRerankResult(candidates=[], diagnostics=diagnostics)

        query_vec = self._encode([q])[0]
        query_literal = self._vector_literal(query_vec)

        candidate_rows = []
        for hit in lexical_hits:
            result_type = str(hit.get("result_type") or "")
            if result_type != "meeting":
                continue
            db_id = hit.get("db_id")
            if db_id is None:
                raw_id = str(hit.get("id") or "")
                if raw_id.startswith("doc_"):
                    try:
                        db_id = int(raw_id.split("_", 1)[1])
                    except (IndexError, ValueError):
                        db_id = None
            catalog_id = hit.get("catalog_id")
            if db_id is None or catalog_id is None:
                continue
            candidate_rows.append(
                {
                    "db_id": int(db_id),
                    "catalog_id": int(catalog_id),
                    "meta": {
                        "result_type": "meeting",
                        "catalog_id": int(catalog_id),
                        "db_id": int(db_id),
                        "event_id": hit.get("event_id"),
                        "city": str(hit.get("city") or "").lower(),
                        "meeting_category": hit.get("meeting_category") or "Other",
                        "organization": hit.get("organization") or "City Council",
                        "date": hit.get("date"),
                        "source_type": "summary",
                    },
                }
            )
        diagnostics["eligible_meeting_candidates"] = len(candidate_rows)
        if not candidate_rows:
            diagnostics["degraded_to_lexical"] = True
            diagnostics["skipped_reason"] = "no_meeting_candidates"
            return SemanticRerankResult(candidates=[], diagnostics=diagnostics)

        by_catalog: dict[int, dict] = {}
        for row in candidate_rows:
            catalog_id = int(row["catalog_id"])
            if catalog_id not in by_catalog:
                by_catalog[catalog_id] = row
        catalog_ids = list(by_catalog.keys())[: max(1, semantic_index.SEMANTIC_RERANK_CANDIDATE_LIMIT)]
        diagnostics["candidate_limit_applied"] = len(catalog_ids)
        if not catalog_ids:
            diagnostics["degraded_to_lexical"] = True
            diagnostics["skipped_reason"] = "no_candidate_catalogs"
            return SemanticRerankResult(candidates=[], diagnostics=diagnostics)

        expected_hash_rows = (
            db.query(Catalog.id, Catalog.summary)
            .filter(Catalog.id.in_(catalog_ids))
            .all()
        )
        expected_hash_by_catalog = {
            int(catalog_id): catalog_semantic_source_hash(summary)
            for catalog_id, summary in expected_hash_rows
        }

        stmt = (
            text(
                """
                SELECT
                  se.catalog_id AS catalog_id,
                  se.source_hash AS source_hash,
                  (1 - (se.embedding <=> CAST(:query_vec AS vector))) AS score
                FROM semantic_embedding se
                WHERE se.catalog_id IN :catalog_ids
                  AND se.model_name = :model_name
                  AND se.embedding IS NOT NULL
                ORDER BY se.embedding <=> CAST(:query_vec AS vector)
                LIMIT :limit
                """
            )
            .bindparams(bindparam("catalog_ids", expanding=True))
        )
        scored_rows = list(
            db.execute(
                stmt,
                {
                    "query_vec": query_literal,
                    "catalog_ids": catalog_ids,
                    "model_name": semantic_index.SEMANTIC_MODEL_NAME,
                    "limit": max(1, len(catalog_ids)),
                },
            ).mappings()
        )

        candidates: list[SemanticCandidate] = []
        seen_catalogs: set[int] = set()
        for row in scored_rows:
            catalog_id = int(row["catalog_id"])
            expected_hash = expected_hash_by_catalog.get(catalog_id)
            actual_hash = row.get("source_hash")
            if expected_hash is None or actual_hash != expected_hash:
                diagnostics["stale_embeddings"] += 1
                continue
            base = by_catalog.get(catalog_id)
            if not base or catalog_id in seen_catalogs:
                continue
            seen_catalogs.add(catalog_id)
            candidates.append(
                SemanticCandidate(
                    row_id=len(candidates),
                    score=float(row.get("score") or 0.0),
                    metadata=base["meta"],
                )
            )

        diagnostics["fresh_embeddings"] = len(candidates)
        diagnostics["missing_embeddings"] = max(0, len(catalog_ids) - len(scored_rows))

        if not candidates:
            diagnostics["degraded_to_lexical"] = True
            if diagnostics["missing_embeddings"] > 0 and diagnostics["stale_embeddings"] == 0:
                diagnostics["skipped_reason"] = "missing_embeddings"
            elif diagnostics["stale_embeddings"] > 0 and diagnostics["missing_embeddings"] == 0:
                diagnostics["skipped_reason"] = "stale_embeddings"
            else:
                diagnostics["skipped_reason"] = "insufficient_fresh_embeddings"
            return SemanticRerankResult(candidates=[], diagnostics=diagnostics)

        diagnostics["hybrid_rerank_applied"] = True
        diagnostics["degraded_to_lexical"] = len(candidates) < min(max(1, int(top_k)), len(catalog_ids))
        if diagnostics["degraded_to_lexical"] and diagnostics["skipped_reason"] is None:
            diagnostics["skipped_reason"] = "partial_embedding_coverage"
        return SemanticRerankResult(
            candidates=candidates[: max(1, int(top_k))],
            diagnostics=diagnostics,
        )

    def rerank_candidates(self, db, query_text: str, lexical_hits: list[dict], top_k: int) -> list[SemanticCandidate]:
        return self.rerank_candidates_with_diagnostics(db, query_text, lexical_hits, top_k).candidates

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "engine": "pgvector", "model_name": _semantic_index_facade().SEMANTIC_MODEL_NAME}
