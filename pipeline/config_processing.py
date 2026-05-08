from __future__ import annotations

from dataclasses import dataclass

from pipeline.config_env import env_bool, env_choice, env_float, env_int, env_stripped


AGENDA_SEGMENTATION_MODE_VALUES = frozenset({"balanced", "aggressive", "recall"})
PIPELINE_RUNTIME_PROFILE_VALUES = frozenset({"", "onboarding_fast"})


@dataclass(frozen=True, slots=True)
class ProcessingConfig:
    max_content_length: int
    max_summary_text_length: int
    nlp_max_text_length: int
    nlp_entity_agenda_max_text: int
    nlp_entity_nonagenda_max_text: int
    nlp_entity_prefix_fallback_text: int
    nlp_entity_min_capitalized_name_cues: int
    entity_backfill_in_process_threshold: int
    max_file_size_bytes: int
    file_write_chunk_size: int
    download_timeout_seconds: int
    download_workers: int
    meilisearch_batch_size: int
    document_chunk_size: int
    max_workers: int
    pipeline_cpu_fraction: float
    db_retry_delay_min: int
    db_retry_delay_max: int
    extraction_terminal_failure_max_attempts: int
    agenda_batch_size: int
    agenda_fallback_max_items_per_doc: int
    agenda_fallback_max_items_per_page_paragraph: int
    agenda_fallback_max_consecutive_rejects_per_page: int
    agenda_segmentation_mode: str
    agenda_min_title_chars: int
    agenda_min_substantive_desc_chars: int
    agenda_toc_dedup_fuzz: int
    agenda_procedural_reject_enabled: bool
    extraction_batch_size: int
    legistar_event_items_capability_ttl_seconds: int
    pipeline_onboarding_city: str
    pipeline_onboarding_started_at_utc: str
    pipeline_onboarding_document_chunk_size: int
    pipeline_onboarding_max_workers: int
    pipeline_runtime_profile: str
    tika_timeout_seconds: int
    tika_ocr_fallback_enabled: bool
    tika_min_extracted_chars_for_no_ocr: int
    tika_pdf_spacing_tolerance: str
    tika_pdf_avg_char_tolerance: str
    tika_retry_backoff_multiplier: int
    text_repair_enable_llm_escalation: bool
    text_repair_llm_max_lines_per_doc: int
    text_repair_min_implausibility_score: float


def load_processing_config() -> ProcessingConfig:
    return ProcessingConfig(
        max_content_length=50000,
        max_summary_text_length=50000,
        nlp_max_text_length=100000,
        nlp_entity_agenda_max_text=env_int("NLP_ENTITY_AGENDA_MAX_TEXT", 24000),
        nlp_entity_nonagenda_max_text=env_int("NLP_ENTITY_NONAGENDA_MAX_TEXT", 16000),
        nlp_entity_prefix_fallback_text=env_int("NLP_ENTITY_PREFIX_FALLBACK_TEXT", 12000),
        nlp_entity_min_capitalized_name_cues=env_int("NLP_ENTITY_MIN_CAPITALIZED_NAME_CUES", 2),
        entity_backfill_in_process_threshold=env_int("ENTITY_BACKFILL_IN_PROCESS_THRESHOLD", 16),
        max_file_size_bytes=104857600,
        file_write_chunk_size=8192,
        download_timeout_seconds=30,
        download_workers=5,
        meilisearch_batch_size=20,
        document_chunk_size=20,
        max_workers=5,
        pipeline_cpu_fraction=0.75,
        db_retry_delay_min=1,
        db_retry_delay_max=3,
        extraction_terminal_failure_max_attempts=env_int("EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS", 3),
        agenda_batch_size=10,
        agenda_fallback_max_items_per_doc=env_int("AGENDA_FALLBACK_MAX_ITEMS_PER_DOC", 200),
        agenda_fallback_max_items_per_page_paragraph=env_int(
            "AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH",
            25,
        ),
        agenda_fallback_max_consecutive_rejects_per_page=env_int(
            "AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE",
            15,
        ),
        agenda_segmentation_mode=env_choice("AGENDA_SEGMENTATION_MODE", "balanced", AGENDA_SEGMENTATION_MODE_VALUES),
        agenda_min_title_chars=env_int("AGENDA_MIN_TITLE_CHARS", 10),
        agenda_min_substantive_desc_chars=env_int("AGENDA_MIN_SUBSTANTIVE_DESC_CHARS", 24),
        agenda_toc_dedup_fuzz=env_int("AGENDA_TOC_DEDUP_FUZZ", 92),
        agenda_procedural_reject_enabled=env_bool("AGENDA_PROCEDURAL_REJECT_ENABLED", True),
        extraction_batch_size=10,
        legistar_event_items_capability_ttl_seconds=env_int("LEGISTAR_EVENT_ITEMS_CAPABILITY_TTL_SECONDS", 3600),
        pipeline_onboarding_city=env_stripped("PIPELINE_ONBOARDING_CITY", ""),
        pipeline_onboarding_started_at_utc=env_stripped("PIPELINE_ONBOARDING_STARTED_AT_UTC", ""),
        pipeline_onboarding_document_chunk_size=env_int("PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE", 0),
        pipeline_onboarding_max_workers=env_int("PIPELINE_ONBOARDING_MAX_WORKERS", 0),
        pipeline_runtime_profile=env_choice("PIPELINE_RUNTIME_PROFILE", "", PIPELINE_RUNTIME_PROFILE_VALUES),
        tika_timeout_seconds=60,
        tika_ocr_fallback_enabled=env_bool("TIKA_OCR_FALLBACK_ENABLED", False),
        tika_min_extracted_chars_for_no_ocr=env_int("TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR", 800),
        tika_pdf_spacing_tolerance=env_stripped("TIKA_PDF_SPACING_TOLERANCE", ""),
        tika_pdf_avg_char_tolerance=env_stripped("TIKA_PDF_AVG_CHAR_TOLERANCE", ""),
        tika_retry_backoff_multiplier=2,
        text_repair_enable_llm_escalation=env_bool("TEXT_REPAIR_ENABLE_LLM_ESCALATION", False),
        text_repair_llm_max_lines_per_doc=env_int("TEXT_REPAIR_LLM_MAX_LINES_PER_DOC", 10),
        text_repair_min_implausibility_score=env_float("TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE", "0.65"),
    )
