from api.main import _build_meilisearch_filter_clauses
from api.search.query_builder import build_meili_filter_clauses, normalize_filters


def test_query_builder_matches_api_wrapper_contract():
    params = dict(
        city="Berkeley",
        meeting_type="Special",
        org="City Council",
        date_from="2026-01-01",
        date_to="2026-01-31",
        include_agenda_items=False,
    )
    wrapper = _build_meilisearch_filter_clauses(**params)
    builder = build_meili_filter_clauses(normalize_filters(**params))
    assert wrapper == builder
