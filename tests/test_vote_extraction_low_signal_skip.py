from types import SimpleNamespace

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
