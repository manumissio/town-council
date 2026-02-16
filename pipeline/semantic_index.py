from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing
import os
import threading
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    SEMANTIC_ALLOW_MULTIPROCESS,
    SEMANTIC_BACKEND,
    SEMANTIC_CONTENT_MAX_CHARS,
    SEMANTIC_INDEX_DIR,
    SEMANTIC_MODEL_NAME,
    SEMANTIC_REQUIRE_SINGLE_PROCESS,
)
from pipeline.models import AgendaItem, Catalog, Document, Event, Organization, Place

logger = logging.getLogger("semantic-index")

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None


class SemanticConfigError(RuntimeError):
    """Raised for unsafe or unsupported semantic backend configuration."""


@dataclass
class SemanticCandidate:
    row_id: int
    score: float
    metadata: dict[str, Any]


@dataclass
class BuildResult:
    row_count: int
    catalog_count: int
    source_counts: dict[str, int]
    corpus_hash: str
    model_name: str
    built_at: str


class SemanticBackend:
    def build_index(self, db) -> BuildResult:  # pragma: no cover - interface
        raise NotImplementedError

    def query(self, query_text: str, top_k: int) -> list[SemanticCandidate]:  # pragma: no cover - interface
        raise NotImplementedError

    def health(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


def _looks_like_multiprocess_worker() -> bool:
    """
    Local embedding and FAISS index memory is process-local.
    We fail fast by default when a runtime looks multiprocess to avoid OOM surprises.
    """
    try:
        if multiprocessing.current_process().name != "MainProcess":
            return True
    except Exception:
        pass

    for key in ("UVICORN_WORKERS", "WEB_CONCURRENCY", "WORKER_CONCURRENCY"):
        val = os.getenv(key)
        if not val:
            continue
        try:
            if int(val) > 1:
                return True
        except ValueError:
            continue
    return False


def _safe_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _build_chunks_from_content(content: str, max_chars: int) -> list[str]:
    """
    We chunk fallback text instead of embedding only the first N chars.
    That keeps later meeting sections searchable when summaries are missing.
    """
    text = _safe_text(content)
    if not text:
        return []
    hard_limited = text[: max_chars * 3]
    words = hard_limited.split()
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for w in words:
        add_len = len(w) + (1 if current else 0)
        if current and current_len + add_len > max_chars:
            chunks.append(" ".join(current))
            current = [w]
            current_len = len(w)
            continue
        current.append(w)
        current_len += add_len
    if current:
        chunks.append(" ".join(current))
    return chunks[:5]


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
                    cls._instance._metadata = []
                    cls._instance._meta = {}
        return cls._instance

    def _guard_runtime(self) -> None:
        if SEMANTIC_ALLOW_MULTIPROCESS:
            return
        if SEMANTIC_REQUIRE_SINGLE_PROCESS and _looks_like_multiprocess_worker():
            raise SemanticConfigError(
                "Unsafe semantic backend configuration detected (multiprocess runtime). "
                "Use a single worker/process for FAISS mode or set SEMANTIC_ALLOW_MULTIPROCESS=true explicitly."
            )

    def _index_path(self) -> Path:
        return Path(SEMANTIC_INDEX_DIR)

    def _ensure_model(self):
        self._guard_runtime()
        if self._model is not None:
            return self._model
        if SentenceTransformer is None:
            raise SemanticConfigError("sentence-transformers is not installed in this environment.")
        with self._lock:
            if self._model is None:
                self._model = SentenceTransformer(SEMANTIC_MODEL_NAME)
        return self._model

    def _encode(self, texts: list[str]) -> np.ndarray:
        model = self._ensure_model()
        vectors = model.encode(texts, batch_size=32, show_progress_bar=False)
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if faiss is not None:
            faiss.normalize_L2(arr)
        return arr

    def _artifact_paths(self) -> dict[str, Path]:
        base = self._index_path()
        return {
            "dir": base,
            "faiss": base / "semantic_index.faiss",
            "ids": base / "semantic_ids.json",
            "meta": base / "semantic_meta.json",
        }

    def _load_artifacts(self) -> None:
        self._guard_runtime()
        if self._index is not None and self._metadata:
            return
        if faiss is None:
            raise SemanticConfigError("faiss-cpu is not installed in this environment.")
        paths = self._artifact_paths()
        if not paths["faiss"].exists() or not paths["ids"].exists() or not paths["meta"].exists():
            raise FileNotFoundError("Semantic artifacts are missing. Run `python reindex_semantic.py`.")
        with self._lock:
            if self._index is None:
                self._index = faiss.read_index(str(paths["faiss"]))
                self._metadata = json.loads(paths["ids"].read_text(encoding="utf-8"))
                self._meta = json.loads(paths["meta"].read_text(encoding="utf-8"))

    def _write_artifacts(self, vectors: np.ndarray, metadata_rows: list[dict[str, Any]], build_meta: dict[str, Any]) -> None:
        if faiss is None:
            raise SemanticConfigError("faiss-cpu is not installed in this environment.")
        paths = self._artifact_paths()
        paths["dir"].mkdir(parents=True, exist_ok=True)

        temp_faiss = paths["faiss"].with_suffix(".faiss.tmp")
        temp_ids = paths["ids"].with_suffix(".json.tmp")
        temp_meta = paths["meta"].with_suffix(".json.tmp")

        dim = vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)
        faiss.write_index(index, str(temp_faiss))
        temp_ids.write_text(json.dumps(metadata_rows, ensure_ascii=False), encoding="utf-8")
        temp_meta.write_text(json.dumps(build_meta, ensure_ascii=False), encoding="utf-8")

        # Atomic rename avoids serving partially-written artifacts while a rebuild is in-flight.
        os.replace(temp_faiss, paths["faiss"])
        os.replace(temp_ids, paths["ids"])
        os.replace(temp_meta, paths["meta"])

    def _collect_rows(self, db) -> tuple[list[str], list[dict[str, Any]], dict[str, int]]:
        texts: list[str] = []
        rows: list[dict[str, Any]] = []
        source_counts = {"summary": 0, "agenda_item": 0, "content_chunk": 0, "agenda_item_result": 0}

        query = (
            db.query(Document, Catalog, Event, Place, Organization)
            .join(Catalog, Document.catalog_id == Catalog.id)
            .join(Event, Document.event_id == Event.id)
            .join(Place, Document.place_id == Place.id)
            .outerjoin(Organization, Event.organization_id == Organization.id)
            .filter(Catalog.content.isnot(None), Catalog.content != "")
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

            summary = _safe_text(catalog.summary)
            extractive = _safe_text(catalog.summary_extractive)
            agenda_items_for_catalog = (
                db.query(AgendaItem)
                .filter(AgendaItem.catalog_id == catalog.id)
                .order_by(AgendaItem.order)
                .all()
            )
            if summary:
                texts.append(summary[:SEMANTIC_CONTENT_MAX_CHARS])
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
                texts.append(extractive[:SEMANTIC_CONTENT_MAX_CHARS])
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
            else:
                if agenda_items_for_catalog:
                    for item in agenda_items_for_catalog:
                        chunk = _safe_text(f"{item.title or ''}. {item.description or ''}")
                        if len(chunk) < 20:
                            continue
                        texts.append(chunk[:SEMANTIC_CONTENT_MAX_CHARS])
                        rows.append(
                            {
                                "result_type": "meeting",
                                "db_id": doc.id,
                                "event_id": event.id,
                                "source_type": "agenda_item",
                                "agenda_item_id": item.id,
                                **base_meta,
                            }
                        )
                        source_counts["agenda_item"] += 1
                else:
                    for chunk in _build_chunks_from_content(catalog.content or "", SEMANTIC_CONTENT_MAX_CHARS):
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
            for item in agenda_items_for_catalog:
                item_text = _safe_text(f"{item.title or ''}. {item.description or ''}")
                if len(item_text) < 20:
                    continue
                texts.append(item_text[:SEMANTIC_CONTENT_MAX_CHARS])
                rows.append(
                    {
                        "result_type": "agenda_item",
                        "db_id": item.id,
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
        texts, rows, source_counts = self._collect_rows(db)
        if not texts:
            raise SemanticConfigError("No semantic rows available to index.")

        vectors = self._encode(texts)
        source_payload = json.dumps(rows, sort_keys=True).encode("utf-8")
        corpus_hash = hashlib.sha256(source_payload).hexdigest()
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        build_meta = {
            "model_name": SEMANTIC_MODEL_NAME,
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
            self._metadata = []
            self._meta = {}
        self._load_artifacts()

        return BuildResult(
            row_count=build_meta["row_count"],
            catalog_count=build_meta["catalog_count"],
            source_counts=source_counts,
            corpus_hash=corpus_hash,
            model_name=SEMANTIC_MODEL_NAME,
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
        scores, indices = self._index.search(query_vec, k)
        out: list[SemanticCandidate] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            row = self._metadata[idx]
            out.append(
                SemanticCandidate(
                    row_id=int(row.get("row_id", idx)),
                    score=float(score),
                    metadata=row,
                )
            )
        return out

    def health(self) -> dict[str, Any]:
        # Guardrail errors are configuration bugs; surface them immediately.
        self._guard_runtime()
        try:
            self._load_artifacts()
            return {
                "status": "ok",
                "row_count": len(self._metadata),
                "model_name": self._meta.get("model_name"),
                "built_at": self._meta.get("built_at"),
            }
        except Exception as exc:
            return {"status": "error", "error": exc.__class__.__name__, "detail": str(exc)}


class PgvectorSemanticBackend(SemanticBackend):
    def build_index(self, db) -> BuildResult:
        raise SemanticConfigError(
            "pgvector backend is not implemented yet. Use SEMANTIC_BACKEND=faiss for Milestone B1."
        )

    def query(self, query_text: str, top_k: int) -> list[SemanticCandidate]:
        raise SemanticConfigError(
            "pgvector backend is not implemented yet. Use SEMANTIC_BACKEND=faiss for Milestone B1."
        )

    def health(self) -> dict[str, Any]:
        return {"status": "not_implemented", "backend": "pgvector"}


def get_semantic_backend() -> SemanticBackend:
    backend = (SEMANTIC_BACKEND or "faiss").strip().lower()
    if backend == "pgvector":
        return PgvectorSemanticBackend()
    return FaissSemanticBackend()
