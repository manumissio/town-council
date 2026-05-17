from __future__ import annotations

from dataclasses import dataclass

from pipeline.config_env import env_bool, env_choice, env_float, env_int, env_nonempty_stripped, env_required_choice


LOCAL_AI_BACKEND_VALUES = frozenset({"inprocess", "http"})
LOCAL_AI_HTTP_API_VALUES = frozenset({"ollama", "openai_compat"})
LOCAL_AI_HTTP_PROFILE_VALUES = frozenset({"conservative", "balanced"})
AGENDA_SUMMARY_PROFILE_VALUES = frozenset({"decision_brief", "item_digest", "risk_first"})
AGENDA_SUMMARY_SINGLE_ITEM_MODE_VALUES = frozenset({"deep_brief", "minimal"})


@dataclass(frozen=True, slots=True)
class InferenceConfig:
    local_ai_allow_multiprocess: bool
    local_ai_require_solo_pool: bool
    local_ai_backend: str
    local_ai_http_api: str
    local_ai_http_base_url: str
    local_ai_http_profile: str
    local_ai_http_timeout_seconds: int
    local_ai_http_timeout_segment_seconds: int
    local_ai_http_timeout_summary_seconds: int
    local_ai_http_timeout_topics_seconds: int
    agenda_segment_maintenance_timeout_seconds: int
    summary_hydration_maintenance_timeout_seconds: int
    local_ai_http_max_retries: int
    local_ai_http_model: str
    city_segmentation_workers: int
    llm_context_window: int
    llm_summary_max_text: int
    llm_summary_max_tokens: int
    llm_agenda_max_text: int
    llm_agenda_max_tokens: int
    enable_vote_extraction: bool
    vote_extraction_max_tokens: int
    vote_extraction_min_text_chars: int
    vote_extraction_confidence_threshold: float
    vote_extraction_context_before_chars: int
    vote_extraction_context_after_chars: int
    summary_min_chars: int
    summary_min_distinct_tokens: int
    summary_max_boilerplate_ratio: float
    topics_min_chars: int
    topics_min_distinct_tokens: int
    summary_grounding_min_coverage: float
    agenda_summary_profile: str
    agenda_summary_min_item_desc_chars: int
    agenda_summary_max_bullets: int
    agenda_summary_single_item_mode: str
    agenda_summary_temperature: float
    agenda_summary_max_input_chars: int
    agenda_summary_min_reserved_output_chars: int


def _profile_timeout_default(profile: str) -> str:
    return "60" if profile == "conservative" else "45"


def _profile_retries_default(profile: str) -> str:
    return "0" if profile == "conservative" else "1"


def load_inference_config() -> InferenceConfig:
    backend = env_choice("LOCAL_AI_BACKEND", "http", LOCAL_AI_BACKEND_VALUES)
    http_api = env_required_choice("LOCAL_AI_HTTP_API", "ollama", LOCAL_AI_HTTP_API_VALUES)
    profile = env_choice("LOCAL_AI_HTTP_PROFILE", "conservative", LOCAL_AI_HTTP_PROFILE_VALUES)
    timeout_seconds = env_int("LOCAL_AI_HTTP_TIMEOUT_SECONDS", _profile_timeout_default(profile))
    return InferenceConfig(
        local_ai_allow_multiprocess=env_bool("LOCAL_AI_ALLOW_MULTIPROCESS", False),
        local_ai_require_solo_pool=env_bool("LOCAL_AI_REQUIRE_SOLO_POOL", True),
        local_ai_backend=backend,
        local_ai_http_api=http_api,
        local_ai_http_base_url=env_nonempty_stripped(
            "LOCAL_AI_HTTP_BASE_URL",
            "http://inference:11434",
        ).rstrip("/"),
        local_ai_http_profile=profile,
        local_ai_http_timeout_seconds=timeout_seconds,
        local_ai_http_timeout_segment_seconds=env_int(
            "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS",
            timeout_seconds,
        ),
        local_ai_http_timeout_summary_seconds=env_int(
            "LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS",
            timeout_seconds,
        ),
        local_ai_http_timeout_topics_seconds=env_int(
            "LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS",
            timeout_seconds,
        ),
        agenda_segment_maintenance_timeout_seconds=env_int(
            "AGENDA_SEGMENT_MAINTENANCE_TIMEOUT_SECONDS",
            30,
        ),
        summary_hydration_maintenance_timeout_seconds=env_int(
            "SUMMARY_HYDRATION_MAINTENANCE_TIMEOUT_SECONDS",
            25,
        ),
        local_ai_http_max_retries=env_int(
            "LOCAL_AI_HTTP_MAX_RETRIES",
            _profile_retries_default(profile),
        ),
        local_ai_http_model=env_nonempty_stripped(
            "LOCAL_AI_HTTP_MODEL",
            "gemma-3-270m-custom",
        ),
        city_segmentation_workers=env_int("CITY_SEGMENTATION_WORKERS", "2" if backend == "http" else "1"),
        llm_context_window=env_int("LLM_CONTEXT_WINDOW", 16384),
        llm_summary_max_text=env_int("LLM_SUMMARY_MAX_TEXT", 30000),
        llm_summary_max_tokens=env_int("LLM_SUMMARY_MAX_TOKENS", 512),
        llm_agenda_max_text=env_int("LLM_AGENDA_MAX_TEXT", 40000),
        llm_agenda_max_tokens=1500,
        enable_vote_extraction=env_bool("ENABLE_VOTE_EXTRACTION", False),
        vote_extraction_max_tokens=env_int("VOTE_EXTRACTION_MAX_TOKENS", 256),
        vote_extraction_min_text_chars=env_int("VOTE_EXTRACTION_MIN_TEXT_CHARS", 200),
        vote_extraction_confidence_threshold=env_float("VOTE_EXTRACTION_CONFIDENCE_THRESHOLD", "0.70"),
        vote_extraction_context_before_chars=env_int("VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS", 500),
        vote_extraction_context_after_chars=env_int("VOTE_EXTRACTION_CONTEXT_AFTER_CHARS", 1000),
        summary_min_chars=env_int("SUMMARY_MIN_CHARS", 80),
        summary_min_distinct_tokens=env_int("SUMMARY_MIN_DISTINCT_TOKENS", 8),
        summary_max_boilerplate_ratio=env_float("SUMMARY_MAX_BOILERPLATE_RATIO", "0.85"),
        topics_min_chars=env_int("TOPICS_MIN_CHARS", 100),
        topics_min_distinct_tokens=env_int("TOPICS_MIN_DISTINCT_TOKENS", 10),
        summary_grounding_min_coverage=env_float("SUMMARY_GROUNDING_MIN_COVERAGE", "0.45"),
        agenda_summary_profile=env_choice(
            "AGENDA_SUMMARY_PROFILE",
            "decision_brief",
            AGENDA_SUMMARY_PROFILE_VALUES,
        ),
        agenda_summary_min_item_desc_chars=env_int("AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS", 24),
        agenda_summary_max_bullets=env_int("AGENDA_SUMMARY_MAX_BULLETS", 10),
        agenda_summary_single_item_mode=env_choice(
            "AGENDA_SUMMARY_SINGLE_ITEM_MODE",
            "deep_brief",
            AGENDA_SUMMARY_SINGLE_ITEM_MODE_VALUES,
        ),
        agenda_summary_temperature=env_float("AGENDA_SUMMARY_TEMPERATURE", "0.3"),
        agenda_summary_max_input_chars=env_int("AGENDA_SUMMARY_MAX_INPUT_CHARS", 12000),
        agenda_summary_min_reserved_output_chars=env_int("AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS", 2000),
    )
