from pathlib import Path

import api.search_support as search_support


def test_search_support_facade_preserves_route_patch_points():
    expected_names = {
        "client",
        "httpx",
        "search_client",
        "facade_callable",
        "facade_value",
        "validate_date_format",
        "_build_filter_values",
        "_build_meilisearch_filter_clauses",
        "_collect_meeting_docs",
        "_count_topics_from_docs",
        "_facet_topics",
        "_iter_time_buckets",
        "_normalize_city_or_400",
        "_normalize_filters_or_400",
        "_parse_iso_date",
        "_require_trends_feature",
        "_semantic_service_get_json",
        "_semantic_service_healthcheck",
    }

    for name in expected_names:
        assert hasattr(search_support, name), name


def test_search_support_modules_stay_under_size_budget():
    paths = [
        Path("api/search_support.py"),
        Path("api/search/filter_support.py"),
        Path("api/search/semantic_support.py"),
        Path("api/search/support_core.py"),
        Path("api/search/trends_support.py"),
    ]

    for path in paths:
        assert len(path.read_text(encoding="utf-8").splitlines()) < 300, path
