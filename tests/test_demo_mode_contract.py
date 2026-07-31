import json
from pathlib import Path


DEMO_DIR = Path("frontend/public/demo")
DEMO_API_MODULE = Path("frontend/lib/api.js")
RETIRED_PERSON_FIXTURES = tuple(f"person_{person_id}.json" for person_id in range(1, 5))


def _load_json(name):
    return json.loads((DEMO_DIR / name).read_text(encoding="utf-8"))


def test_demo_fixture_files_exist():
    expected_files = [
        "metadata.json",
        "search.json",
        "catalog_701_content.json",
        "catalog_702_content.json",
        "catalog_703_content.json",
        "catalog_701_derived_status.json",
        "catalog_702_derived_status.json",
        "catalog_703_derived_status.json",
        "catalog_batch.json",
    ]
    for file_name in expected_files:
        assert (DEMO_DIR / file_name).exists(), f"Missing demo fixture: {file_name}"


def test_demo_mode_has_no_people_detail_routes_or_fixtures():
    demo_api_source = DEMO_API_MODULE.read_text(encoding="utf-8")

    assert "/person/" not in demo_api_source
    for person_fixture in RETIRED_PERSON_FIXTURES:
        assert not (DEMO_DIR / person_fixture).exists()


def test_search_fixture_has_required_hit_keys():
    search_fixture = _load_json("search.json")
    assert "hits" in search_fixture
    assert isinstance(search_fixture["hits"], list)
    assert search_fixture["hits"], "search.json must contain at least one hit"

    required_hit_keys = {"id", "catalog_id", "event_name", "city", "date", "filename", "url", "content"}
    for hit in search_fixture["hits"]:
        assert required_hit_keys.issubset(hit.keys())
        assert "people_metadata" not in hit


def test_derived_status_fixtures_have_state_flags():
    for catalog_id in (701, 702, 703):
        status = _load_json(f"catalog_{catalog_id}_derived_status.json")
        required_keys = {
            "summary_is_stale",
            "topics_is_stale",
            "summary_not_generated_yet",
            "topics_not_generated_yet",
            "agenda_not_generated_yet",
        }
        assert required_keys.issubset(status.keys())
