from types import SimpleNamespace

from pipeline.vote_extraction_contracts import (
    SKIP_REASON_ALREADY_HIGH_CONFIDENCE,
    SKIP_REASON_EXISTING_RESULT,
    SKIP_REASON_MISSING_TITLE,
    SKIP_REASON_TRUSTED_SOURCE,
    VoteExtractionRuntimeHooks,
    VoteExtractionSettings,
)
from pipeline.vote_extraction_item import skip_reason_before_extraction
from pipeline.vote_extractor import run_vote_extraction_for_catalog


class _StubLocalAI:
    def generate_json(self, prompt: str, max_tokens: int = 256):
        return '{"outcome_label":"passed","motion_text":null,"vote_tally_raw":null,"yes_count":null,"no_count":null,"abstain_count":null,"absent_count":null,"confidence":0.95,"evidence_snippet":null}'


def test_short_context_skips_vote_extraction():
    item = SimpleNamespace(
        id=11,
        title="Item 1",
        description="Short",
        result="",
        votes=None,
    )
    catalog = SimpleNamespace(id=2, content="Too short")
    doc = SimpleNamespace(category="minutes", event=SimpleNamespace(name="Council", record_date="2026-01-10"))

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=_StubLocalAI(),
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["processed_items"] == 0
    assert counters["updated_items"] == 0
    assert counters["skip_reasons"]["insufficient_text"] == 1


def _settings() -> VoteExtractionSettings:
    return VoteExtractionSettings(
        confidence_threshold=0.7,
        context_after_chars=1000,
        context_before_chars=500,
        max_tokens=256,
        min_text_chars=200,
    )


def test_skip_helper_preserves_pre_extraction_skip_order_and_force_behavior():
    missing_title_item = SimpleNamespace(id=1, title="", description="", result="", votes=None)
    trusted_item = SimpleNamespace(id=2, title="Item", description="", result="", votes={"source": "legistar"})
    existing_result_item = SimpleNamespace(id=3, title="Item", description="", result="Passed", votes=None)
    high_confidence_item = SimpleNamespace(
        id=4,
        title="Item",
        description="",
        result="",
        votes={"source": "llm_extracted", "confidence": 0.95, "outcome_label": "passed"},
    )

    assert (
        skip_reason_before_extraction(
            missing_title_item,
            item_title="",
            force=False,
            settings=_settings(),
            runtime_hooks=VoteExtractionRuntimeHooks(),
        )
        == SKIP_REASON_MISSING_TITLE
    )
    assert (
        skip_reason_before_extraction(
            trusted_item,
            item_title="Item",
            force=True,
            settings=_settings(),
            runtime_hooks=VoteExtractionRuntimeHooks(),
        )
        == SKIP_REASON_TRUSTED_SOURCE
    )
    assert (
        skip_reason_before_extraction(
            high_confidence_item,
            item_title="Item",
            force=False,
            settings=_settings(),
            runtime_hooks=VoteExtractionRuntimeHooks(),
        )
        == SKIP_REASON_ALREADY_HIGH_CONFIDENCE
    )
    assert (
        skip_reason_before_extraction(
            existing_result_item,
            item_title="Item",
            force=False,
            settings=_settings(),
            runtime_hooks=VoteExtractionRuntimeHooks(),
        )
        == SKIP_REASON_EXISTING_RESULT
    )
    assert (
        skip_reason_before_extraction(
            existing_result_item,
            item_title="Item",
            force=True,
            settings=_settings(),
            runtime_hooks=VoteExtractionRuntimeHooks(),
        )
        is None
    )
