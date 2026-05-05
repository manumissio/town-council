import ast
from pathlib import Path

import pytest

from pipeline import vote_extractor
from pipeline.vote_extractor import parse_vote_extraction_response


def test_vote_extractor_facade_exports_current_contract():
    expected_names = [
        "VOTE_EXTRACTION_CONFIDENCE_THRESHOLD",
        "VOTE_EXTRACTION_CONTEXT_AFTER_CHARS",
        "VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS",
        "VOTE_EXTRACTION_MAX_TOKENS",
        "VOTE_EXTRACTION_MIN_TEXT_CHARS",
        "LLM_EXTRACTED_VOTE_SOURCE",
        "SKIP_REASON_MISSING_TITLE",
        "SKIP_REASON_TRUSTED_SOURCE",
        "SKIP_REASON_ALREADY_HIGH_CONFIDENCE",
        "SKIP_REASON_EXISTING_RESULT",
        "SKIP_REASON_INSUFFICIENT_TEXT",
        "SKIP_REASON_LOW_CONFIDENCE",
        "SKIP_REASON_UNKNOWN_NO_TALLY",
        "VALID_OUTCOME_LABELS",
        "OUTCOME_SYNONYMS",
        "UNKNOWN_RESULT_VALUES",
        "TRUSTED_VOTE_SOURCES",
        "VOTE_KEYWORDS",
        "VoteExtractionModel",
        "AgendaItemLike",
        "AgendaItemQuery",
        "AgendaItemSession",
        "CatalogLike",
        "EventLike",
        "DocumentLike",
        "VoteExtractionCounters",
        "VoteExtractionResult",
        "prepare_vote_extraction_prompt",
        "normalize_outcome_label",
        "_extract_first_json_object",
        "_coerce_optional_int",
        "parse_vote_extraction_response",
        "extract_vote_outcome",
        "_build_vote_context_text",
        "_result_text_from_label",
        "_is_high_confidence_existing_llm_vote",
        "_is_trusted_existing_vote",
        "_has_non_unknown_result",
        "_apply_ambiguity_penalty",
        "run_vote_extraction_for_catalog",
        "AgendaItem",
        "logger",
    ]

    missing_names = [name for name in expected_names if not hasattr(vote_extractor, name)]

    assert missing_names == []


def test_vote_extraction_modules_do_not_import_facade():
    module_paths = [
        Path("pipeline/vote_extraction_contracts.py"),
        Path("pipeline/vote_extraction_prompting.py"),
        Path("pipeline/vote_extraction_parser.py"),
        Path("pipeline/vote_extraction_context.py"),
        Path("pipeline/vote_extraction_policy.py"),
        Path("pipeline/vote_extraction_runner.py"),
    ]
    offenders: list[str] = []

    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "pipeline.vote_extractor":
                offenders.append(str(module_path))
            if isinstance(node, ast.Import):
                offenders.extend(str(module_path) for alias in node.names if alias.name == "pipeline.vote_extractor")

    assert offenders == []


def test_parse_vote_extraction_valid_json():
    raw = """
    {
      "outcome_label": "passed",
      "motion_text": "Adopt staff recommendation",
      "vote_tally_raw": "Ayes: 5, Noes: 0",
      "yes_count": 5,
      "no_count": 0,
      "abstain_count": null,
      "absent_count": null,
      "confidence": 0.92,
      "evidence_snippet": "Motion carried with ayes 5 and noes 0."
    }
    """
    parsed = parse_vote_extraction_response(raw, council_size=7)
    assert parsed.outcome_label == "passed"
    assert parsed.yes_count == 5
    assert parsed.no_count == 0
    assert parsed.confidence == pytest.approx(0.92)


def test_parse_vote_extraction_rejects_malformed_json():
    with pytest.raises(ValueError):
        parse_vote_extraction_response('{"outcome_label":"passed"')


def test_parse_vote_extraction_normalizes_synonyms():
    raw = """
    {"outcome_label":"approved unanimously","motion_text":null,"vote_tally_raw":null,
    "yes_count":null,"no_count":null,"abstain_count":null,"absent_count":null,
    "confidence":0.88,"evidence_snippet":null}
    """
    parsed = parse_vote_extraction_response(raw)
    assert parsed.outcome_label == "passed"


def test_parse_vote_extraction_rejects_impossible_tally():
    raw = """
    {"outcome_label":"passed","motion_text":null,"vote_tally_raw":"5-0",
    "yes_count":5,"no_count":0,"abstain_count":0,"absent_count":0,
    "confidence":0.8,"evidence_snippet":null}
    """
    with pytest.raises(ValueError):
        parse_vote_extraction_response(raw, council_size=4)
