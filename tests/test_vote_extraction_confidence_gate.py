from types import SimpleNamespace

from pipeline.vote_extraction_contracts import VoteExtractionResult
from pipeline.vote_extractor import run_vote_extraction_for_catalog


class _StubLocalAI:
    def __init__(self, payload: str):
        self.payload = payload

    def generate_json(self, prompt: str, max_tokens: int = 256):
        return self.payload


def test_low_confidence_does_not_overwrite_existing_result():
    long_context = " ".join(["Motion was seconded and debated."] * 20)
    item = SimpleNamespace(
        id=10,
        title="Budget Motion",
        description=long_context,
        result="Passed",
        votes=None,
    )
    catalog = SimpleNamespace(id=1, content=f"Budget Motion. {long_context}")
    doc = SimpleNamespace(category="minutes", event=SimpleNamespace(name="Council", record_date="2026-01-10"))
    local_ai = _StubLocalAI(
        '{"outcome_label":"failed","motion_text":"Budget motion","vote_tally_raw":"3-2",'
        '"yes_count":3,"no_count":2,"abstain_count":null,"absent_count":null,'
        '"confidence":0.2,"evidence_snippet":"motion failed"}'
    )

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 0
    assert counters["skip_reasons"]["existing_result"] == 1
    assert item.result == "Passed"


def test_facade_confidence_threshold_patch_controls_runner(monkeypatch):
    long_context = " ".join(["Motion was seconded and passed."] * 20)
    item = SimpleNamespace(
        id=10,
        title="Budget Motion",
        description=long_context,
        result="",
        votes=None,
    )
    catalog = SimpleNamespace(id=1, content=f"Budget Motion. {long_context}")
    doc = SimpleNamespace(category="minutes", event=SimpleNamespace(name="Council", record_date="2026-01-10"))
    local_ai = _StubLocalAI(
        '{"outcome_label":"passed","motion_text":"Budget motion","vote_tally_raw":"5-0",'
        '"yes_count":5,"no_count":0,"abstain_count":null,"absent_count":null,'
        '"confidence":0.95,"evidence_snippet":"motion passed"}'
    )

    monkeypatch.setattr("pipeline.vote_extractor.VOTE_EXTRACTION_CONFIDENCE_THRESHOLD", 0.99)

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 0
    assert counters["skip_reasons"]["low_confidence"] == 1
    assert item.result == ""


def test_facade_extractor_patch_controls_runner(monkeypatch):
    long_context = " ".join(["Motion was seconded and passed."] * 20)
    item = SimpleNamespace(
        id=10,
        title="Budget Motion",
        description=long_context,
        result="",
        votes=None,
    )
    catalog = SimpleNamespace(id=1, content=f"Budget Motion. {long_context}")
    doc = SimpleNamespace(category="minutes", event=SimpleNamespace(name="Council", record_date="2026-01-10"))
    local_ai = _StubLocalAI("{}")

    def patched_extract_vote_outcome(local_ai, item_title, item_text, meeting_context=""):
        return VoteExtractionResult(outcome_label="failed", confidence=0.99)

    monkeypatch.setattr("pipeline.vote_extractor.extract_vote_outcome", patched_extract_vote_outcome)

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 1
    assert item.result == "Failed"


def test_facade_parser_patch_reaches_catalog_runner(monkeypatch):
    long_context = " ".join(["Motion was seconded and passed."] * 20)
    item = SimpleNamespace(
        id=10,
        title="Budget Motion",
        description=long_context,
        result="",
        votes=None,
    )
    catalog = SimpleNamespace(id=1, content=f"Budget Motion. {long_context}")
    doc = SimpleNamespace(category="minutes", event=SimpleNamespace(name="Council", record_date="2026-01-10"))
    local_ai = _StubLocalAI("{}")

    def patched_parse_vote_extraction_response(raw_output, council_size=None):
        return VoteExtractionResult(outcome_label="passed", confidence=0.2)

    monkeypatch.setattr(
        "pipeline.vote_extractor.parse_vote_extraction_response", patched_parse_vote_extraction_response
    )

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 0
    assert counters["skip_reasons"]["low_confidence"] == 1
    assert item.result == ""


def test_facade_context_patch_controls_runner(monkeypatch):
    item = SimpleNamespace(id=10, title="Budget Motion", description="", result="", votes=None)
    catalog = SimpleNamespace(id=1, content="")
    doc = SimpleNamespace(category="minutes", event=None)
    local_ai = _StubLocalAI(
        '{"outcome_label":"passed","motion_text":"Budget motion","vote_tally_raw":"5-0",'
        '"yes_count":5,"no_count":0,"abstain_count":null,"absent_count":null,'
        '"confidence":0.95,"evidence_snippet":"motion passed"}'
    )

    monkeypatch.setattr(
        "pipeline.vote_extractor._build_vote_context_text",
        lambda catalog_content, item_title, item_description: " ".join(["Motion passed."] * 30),
    )

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 1
    assert item.result == "Passed"


def test_facade_existing_vote_patch_controls_runner(monkeypatch):
    item = SimpleNamespace(
        id=10, title="Budget Motion", description=" ".join(["Motion passed."] * 30), result="", votes={}
    )
    catalog = SimpleNamespace(id=1, content="")
    doc = SimpleNamespace(category="minutes", event=None)
    local_ai = _StubLocalAI("{}")

    monkeypatch.setattr("pipeline.vote_extractor._is_trusted_existing_vote", lambda votes: True)

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 0
    assert counters["skip_reasons"]["trusted_source"] == 1


def test_facade_high_confidence_patch_controls_runner(monkeypatch):
    item = SimpleNamespace(
        id=10, title="Budget Motion", description=" ".join(["Motion passed."] * 30), result="", votes=None
    )
    catalog = SimpleNamespace(id=1, content="")
    doc = SimpleNamespace(category="minutes", event=None)
    local_ai = _StubLocalAI("{}")

    monkeypatch.setattr("pipeline.vote_extractor._is_high_confidence_existing_llm_vote", lambda votes: True)

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 0
    assert counters["skip_reasons"]["already_high_confidence"] == 1


def test_facade_existing_result_patch_controls_runner(monkeypatch):
    item = SimpleNamespace(
        id=10,
        title="Budget Motion",
        description=" ".join(["Motion passed."] * 30),
        result="Passed",
        votes=None,
    )
    catalog = SimpleNamespace(id=1, content="")
    doc = SimpleNamespace(category="minutes", event=None)
    local_ai = _StubLocalAI(
        '{"outcome_label":"failed","motion_text":"Budget motion","vote_tally_raw":"3-2",'
        '"yes_count":3,"no_count":2,"abstain_count":null,"absent_count":null,'
        '"confidence":0.95,"evidence_snippet":"motion failed"}'
    )

    monkeypatch.setattr("pipeline.vote_extractor._has_non_unknown_result", lambda result_value: False)

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 1
    assert item.result == "Failed"


def test_facade_result_text_patch_controls_runner(monkeypatch):
    item = SimpleNamespace(
        id=10, title="Budget Motion", description=" ".join(["Motion passed."] * 30), result="", votes=None
    )
    catalog = SimpleNamespace(id=1, content="")
    doc = SimpleNamespace(category="minutes", event=None)
    local_ai = _StubLocalAI(
        '{"outcome_label":"passed","motion_text":"Budget motion","vote_tally_raw":"5-0",'
        '"yes_count":5,"no_count":0,"abstain_count":null,"absent_count":null,'
        '"confidence":0.95,"evidence_snippet":"motion passed"}'
    )

    monkeypatch.setattr("pipeline.vote_extractor._result_text_from_label", lambda outcome_label: "Patched Result")

    counters = run_vote_extraction_for_catalog(
        db=None,
        local_ai=local_ai,
        catalog=catalog,
        doc=doc,
        force=False,
        agenda_items=[item],
    )

    assert counters["updated_items"] == 1
    assert item.result == "Patched Result"
