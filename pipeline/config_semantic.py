from __future__ import annotations

from dataclasses import dataclass

from pipeline.config_env import env_bool, env_float, env_int, env_nonempty_lower, env_raw


@dataclass(frozen=True, slots=True)
class SemanticConfig:
    semantic_enabled: bool
    semantic_backend: str
    semantic_model_name: str
    semantic_index_dir: str
    semantic_content_max_chars: int
    semantic_base_top_k: int
    semantic_max_top_k: int
    semantic_filter_expansion_factor: int
    semantic_rerank_candidate_limit: int
    feature_trends_dashboard: bool
    lineage_min_edge_confidence: float
    lineage_require_mutual_edges: bool
    semantic_require_single_process: bool
    semantic_allow_multiprocess: bool
    semantic_require_faiss: bool


def load_semantic_config() -> SemanticConfig:
    return SemanticConfig(
        semantic_enabled=env_bool("SEMANTIC_ENABLED", False),
        semantic_backend=env_nonempty_lower("SEMANTIC_BACKEND", "faiss"),
        semantic_model_name=env_raw("SEMANTIC_MODEL_NAME", "all-MiniLM-L6-v2"),
        semantic_index_dir=env_raw("SEMANTIC_INDEX_DIR", "/data/semantic"),
        semantic_content_max_chars=env_int("SEMANTIC_CONTENT_MAX_CHARS", 4000),
        semantic_base_top_k=env_int("SEMANTIC_BASE_TOP_K", 200),
        semantic_max_top_k=env_int("SEMANTIC_MAX_TOP_K", 10000),
        semantic_filter_expansion_factor=env_int("SEMANTIC_FILTER_EXPANSION_FACTOR", 8),
        semantic_rerank_candidate_limit=env_int("SEMANTIC_RERANK_CANDIDATE_LIMIT", 200),
        feature_trends_dashboard=env_bool("FEATURE_TRENDS_DASHBOARD", False),
        lineage_min_edge_confidence=env_float("LINEAGE_MIN_EDGE_CONFIDENCE", "0.5"),
        lineage_require_mutual_edges=env_bool("LINEAGE_REQUIRE_MUTUAL_EDGES", False),
        semantic_require_single_process=env_bool("SEMANTIC_REQUIRE_SINGLE_PROCESS", True),
        semantic_allow_multiprocess=env_bool("SEMANTIC_ALLOW_MULTIPROCESS", False),
        semantic_require_faiss=env_bool("SEMANTIC_REQUIRE_FAISS", False),
    )
