from __future__ import annotations

import logging

from pipeline.config import (
    SEMANTIC_ALLOW_MULTIPROCESS,
    SEMANTIC_BACKEND,
    SEMANTIC_CONTENT_MAX_CHARS,
    SEMANTIC_INDEX_DIR,
    SEMANTIC_MODEL_NAME,
    SEMANTIC_RERANK_CANDIDATE_LIMIT,
    SEMANTIC_REQUIRE_FAISS,
    SEMANTIC_REQUIRE_SINGLE_PROCESS,
)
from pipeline.semantic_backend_runtime import _looks_like_multiprocess_worker, get_semantic_backend
from pipeline.semantic_backend_types import (
    BuildResult,
    SemanticBackend,
    SemanticCandidate,
    SemanticConfigError,
    SemanticRerankResult,
)
from pipeline.semantic_faiss_backend import FaissSemanticBackend
from pipeline.semantic_pgvector_backend import PgvectorSemanticBackend
from pipeline.semantic_text import (
    _build_chunks_from_content,
    _safe_text,
    catalog_semantic_source_hash,
    catalog_semantic_text,
)

logger = logging.getLogger("semantic-index")

__all__ = [
    "BuildResult",
    "FaissSemanticBackend",
    "PgvectorSemanticBackend",
    "SEMANTIC_ALLOW_MULTIPROCESS",
    "SEMANTIC_BACKEND",
    "SEMANTIC_CONTENT_MAX_CHARS",
    "SEMANTIC_INDEX_DIR",
    "SEMANTIC_MODEL_NAME",
    "SEMANTIC_RERANK_CANDIDATE_LIMIT",
    "SEMANTIC_REQUIRE_FAISS",
    "SEMANTIC_REQUIRE_SINGLE_PROCESS",
    "SemanticBackend",
    "SemanticCandidate",
    "SemanticConfigError",
    "SemanticRerankResult",
    "SentenceTransformer",
    "_build_chunks_from_content",
    "_looks_like_multiprocess_worker",
    "_safe_text",
    "catalog_semantic_source_hash",
    "catalog_semantic_text",
    "faiss",
    "get_semantic_backend",
]

try:
    import faiss
except ImportError:  # pragma: no cover
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None
