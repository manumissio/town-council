from types import SimpleNamespace

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
