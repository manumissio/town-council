from api.search.query_builder import (
    build_meili_filter_clauses,
    normalize_city_filter,
    normalize_filters,
)


def test_normalize_city_filter_supports_human_label():
    assert normalize_city_filter("Cupertino") == "ca_cupertino"


def test_normalize_city_filter_strips_diacritics_and_normalizes_spacing():
    assert normalize_city_filter(" San Leándro ") == "ca_san_leandro"
    assert normalize_city_filter("ca-san-jose") == "ca_san_jose"


def test_normalize_city_filter_rejects_empty_or_non_alnum_inputs():
    import pytest

    with pytest.raises(ValueError):
        normalize_city_filter("   ")
    with pytest.raises(ValueError):
        normalize_city_filter("!!!")


def test_build_meili_filter_clauses_meeting_only_by_default():
    filters = normalize_filters(
        city="Berkeley",
        meeting_type="  Special  ",
        org=" City   Council ",
        date_from="2026-01-01",
        date_to="2026-02-01",
        include_agenda_items=False,
    )
    clauses = build_meili_filter_clauses(filters)
    assert 'result_type = "meeting"' in clauses
    assert 'city = "ca_berkeley"' in clauses
    assert 'meeting_category = "Special"' in clauses
    assert 'organization = "City Council"' in clauses
    assert any("date >=" in c and "date <=" in c for c in clauses)


def test_normalize_filters_normalizes_meeting_type_and_org_whitespace():
    filters = normalize_filters(
        city="Berkeley",
        meeting_type="  Special   Meeting ",
        org=" City   Council ",
        date_from=None,
        date_to=None,
        include_agenda_items=False,
    )
    assert filters.meeting_type == "Special Meeting"
    assert filters.org == "City Council"


def test_build_meili_filter_clauses_include_agenda_items_true():
    filters = normalize_filters(
        city=None,
        meeting_type=None,
        org=None,
        date_from=None,
        date_to=None,
        include_agenda_items=True,
    )
    clauses = build_meili_filter_clauses(filters)
    assert clauses == []
