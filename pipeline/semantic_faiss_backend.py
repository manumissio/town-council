from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.models import AgendaItem, Catalog, Document, Event, Organization, Place
from pipeline.semantic_backend_types import BuildResult, SemanticBackend, SemanticCandidate, SemanticConfigError
from pipeline.semantic_text import _build_chunks_from_content, _safe_text, catalog_semantic_text

logger = logging.getLogger("semantic-index")


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
        if semantic_index.SEMANTIC_ALLOW_MULTIPROCESS:
            pass
        elif semantic_index.SEMANTIC_REQUIRE_SINGLE_PROCESS and semantic_index._looks_like_multiprocess_worker():
            raise SemanticConfigError(
                "Unsafe semantic backend configuration detected (multiprocess runtime). "
                "Use a single worker/process for FAISS mode or set SEMANTIC_ALLOW_MULTIPROCESS=true explicitly."
            )
        # Operators can force strict FAISS mode when they want predictable performance.
        # Default remains resilient fallback so semantic search still works if FAISS wheels are unavailable.
        if semantic_index.SEMANTIC_REQUIRE_FAISS and semantic_index.faiss is None:
            raise SemanticConfigError(
                "SEMANTIC_REQUIRE_FAISS=true but faiss-cpu is unavailable in this runtime. "
                "Install/repair faiss-cpu or set SEMANTIC_REQUIRE_FAISS=false to allow numpy fallback."
            )

    def _index_path(self) -> Path:
        return Path(_semantic_index_facade().SEMANTIC_INDEX_DIR)

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

    def _artifact_paths(self) -> dict[str, Path]:
        base = self._index_path()
        return {
            "dir": base,
            "faiss": base / "semantic_index.faiss",
            "npy": base / "semantic_index.npy",
            "ids": base / "semantic_ids.json",
            "meta": base / "semantic_meta.json",
        }

    def _load_artifacts(self) -> None:
        self._guard_runtime()
        if self._index is not None and self._metadata:
            return
        paths = self._artifact_paths()
        if not paths["ids"].exists() or not paths["meta"].exists():
            raise FileNotFoundError("Semantic artifacts are missing. Run `python reindex_semantic.py`.")
        with self._lock:
            if self._index is None:
                faiss_backend = _semantic_index_facade().faiss
                self._metadata = json.loads(paths["ids"].read_text(encoding="utf-8"))
                self._meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
                if faiss_backend is not None and paths["faiss"].exists():
                    self._index = faiss_backend.read_index(str(paths["faiss"]))
                    self._matrix = None
                elif paths["npy"].exists():
                    # Fallback path for environments where faiss-cpu wheels are unavailable.
                    # We still support semantic retrieval via normalized cosine-dot search.
                    self._matrix = np.load(paths["npy"], allow_pickle=False)
                    self._index = self._matrix
                else:
                    raise FileNotFoundError(
                        "Semantic index vectors are missing. Run `python reindex_semantic.py`."
                    )

    def _write_artifacts(self, vectors: np.ndarray, metadata_rows: list[dict[str, Any]], build_meta: dict[str, Any]) -> None:
        paths = self._artifact_paths()
        paths["dir"].mkdir(parents=True, exist_ok=True)

        temp_faiss = paths["faiss"].with_suffix(".faiss.tmp")
        temp_npy = paths["npy"].with_suffix(".npy.tmp")
        temp_ids = paths["ids"].with_suffix(".json.tmp")
        temp_meta = paths["meta"].with_suffix(".json.tmp")

        faiss_backend = _semantic_index_facade().faiss
        if faiss_backend is not None:
            dim = vectors.shape[1]
            index = faiss_backend.IndexFlatIP(dim)
            index.add(vectors)
            faiss_backend.write_index(index, str(temp_faiss))
            build_meta["engine"] = "faiss"
        else:
            logger.warning("faiss-cpu is unavailable; using numpy semantic index fallback.")
            with open(temp_npy, "wb") as fh:
                np.save(fh, vectors)
            build_meta["engine"] = "numpy"

        temp_ids.write_text(json.dumps(metadata_rows, ensure_ascii=False), encoding="utf-8")
        temp_meta.write_text(json.dumps(build_meta, ensure_ascii=False), encoding="utf-8")

        # Atomic rename avoids serving partially-written artifacts while a rebuild is in-flight.
        if faiss_backend is not None:
            os.replace(temp_faiss, paths["faiss"])
            if paths["npy"].exists():
                os.remove(paths["npy"])
        else:
            os.replace(temp_npy, paths["npy"])
            if paths["faiss"].exists():
                os.remove(paths["faiss"])
        os.replace(temp_ids, paths["ids"])
        os.replace(temp_meta, paths["meta"])

    def _collect_rows(self, db) -> tuple[list[str], list[dict[str, Any]], dict[str, int]]:
        semantic_index = _semantic_index_facade()
        texts: list[str] = []
        rows: list[dict[str, Any]] = []
        source_counts = {"summary": 0, "agenda_item": 0, "content_chunk": 0, "agenda_item_result": 0}
        agenda_items_by_catalog: dict[int, list[AgendaItem]] = {}

        for agenda_item in (
            db.query(AgendaItem)
            .filter(AgendaItem.catalog_id.isnot(None))
            .order_by(AgendaItem.catalog_id, AgendaItem.order)
            .all()
        ):
            agenda_items_by_catalog.setdefault(int(agenda_item.catalog_id), []).append(agenda_item)

        query = (
            db.query(Document, Catalog, Event, Place, Organization)
            .join(Catalog, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .join(Place, Document.place_id == Place.id)
            .outerjoin(Organization, Event.organization_id == Organization.id)
            .yield_per(50)
        )
        for doc, catalog, event, place, org in query:
            base_meta = {
                "catalog_id": catalog.id,
                "event_id": event.id,
                "date": event.record_date.isoformat() if event.record_date else None,
                "city": (place.display_name or place.name or "").lower(),
                "meeting_category": (event.meeting_type or "Other"),
                "organization": org.name if org else "City Council",
            }

            summary = catalog_semantic_text(catalog.summary)
            extractive = _safe_text(catalog.summary_extractive)
            agenda_items_for_catalog = agenda_items_by_catalog.get(int(catalog.id), [])
            if summary:
                texts.append(summary)
                rows.append(
                    {
                        "result_type": "meeting",
                        "db_id": doc.id,
                        "event_id": event.id,
                        "source_type": "summary",
                        **base_meta,
                    }
                )
                source_counts["summary"] += 1
            elif extractive:
                texts.append(extractive[: semantic_index.SEMANTIC_CONTENT_MAX_CHARS])
                rows.append(
                    {
                        "result_type": "meeting",
                        "db_id": doc.id,
                        "event_id": event.id,
                        "source_type": "summary_extractive",
                        **base_meta,
                    }
                )
                source_counts["summary"] += 1
            elif agenda_items_for_catalog:
                for agenda_item in agenda_items_for_catalog:
                    chunk = _safe_text(f"{agenda_item.title or ''}. {agenda_item.description or ''}")
                    if len(chunk) < 20:
                        continue
                    texts.append(chunk[: semantic_index.SEMANTIC_CONTENT_MAX_CHARS])
                    rows.append(
                        {
                            "result_type": "meeting",
                            "db_id": doc.id,
                            "event_id": event.id,
                            "source_type": "agenda_item",
                            "agenda_item_id": agenda_item.id,
                            **base_meta,
                        }
                    )
                    source_counts["agenda_item"] += 1
            else:
                for chunk in _build_chunks_from_content(catalog.content or "", semantic_index.SEMANTIC_CONTENT_MAX_CHARS):
                    if len(chunk) < 20:
                        continue
                    texts.append(chunk)
                    rows.append(
                        {
                            "result_type": "meeting",
                            "db_id": doc.id,
                            "event_id": event.id,
                            "source_type": "content_chunk",
                            **base_meta,
                        }
                    )
                    source_counts["content_chunk"] += 1

            # Agenda-item vectors are stored separately so semantic mode can optionally
            # return agenda hits instead of only meeting-level parent docs.
            for agenda_item in agenda_items_for_catalog:
                item_text = _safe_text(f"{agenda_item.title or ''}. {agenda_item.description or ''}")
                if len(item_text) < 20:
                    continue
                texts.append(item_text[: semantic_index.SEMANTIC_CONTENT_MAX_CHARS])
                rows.append(
                    {
                        "result_type": "agenda_item",
                        "db_id": agenda_item.id,
                        "event_id": event.id,
                        "source_type": "agenda_item_result",
                        **base_meta,
                    }
                )
                source_counts["agenda_item_result"] += 1

        for row_id, row in enumerate(rows):
            row["row_id"] = row_id
        return texts, rows, source_counts

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

        # Reload fresh artifacts so the active process serves the latest index immediately.
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

        q = _safe_text(query_text)
        if not q:
            return []
        query_vec = self._encode([q])
        k = max(1, min(int(top_k), len(self._metadata)))
        faiss_backend = _semantic_index_facade().faiss
        if faiss_backend is not None and hasattr(self._index, "search"):
            scores, indices = self._index.search(query_vec, k)
        else:
            matrix = self._matrix if self._matrix is not None else np.asarray(self._index, dtype=np.float32)
            sims = np.dot(matrix, query_vec[0])
            # NumPy fallback: select top-k without fully sorting the whole array.
            # This reduces work from O(N log N) to near O(N), then sorts only k items.
            if k >= sims.shape[0]:
                top_idx = np.argsort(-sims)
            else:
                top_idx = np.argpartition(-sims, k - 1)[:k]
                top_idx = top_idx[np.argsort(-sims[top_idx])]
            scores = np.array([sims[top_idx]], dtype=np.float32)
            indices = np.array([top_idx], dtype=np.int64)
        semantic_candidates: list[SemanticCandidate] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            row = self._metadata[idx]
            semantic_candidates.append(
                SemanticCandidate(
                    row_id=int(row.get("row_id", idx)),
                    score=float(score),
                    metadata=row,
                )
            )
        return semantic_candidates

    def health(self) -> dict[str, Any]:
        # Guardrail errors are configuration bugs; surface them immediately.
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
