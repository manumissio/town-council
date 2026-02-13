import json
from pathlib import Path


DEMO_DIR = Path("frontend/public/demo")


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
        "person_1.json",
        "person_2.json",
        "person_3.json",
        "person_4.json",
        "catalog_batch.json",
    ]
    for file_name in expected_files:
        assert (DEMO_DIR / file_name).exists(), f"Missing demo fixture: {file_name}"


def test_search_fixture_has_required_hit_keys():
    data = _load_json("search.json")
    assert "hits" in data
    assert isinstance(data["hits"], list)
    assert data["hits"], "search.json must contain at least one hit"

    required_hit_keys = {"id", "catalog_id", "event_name", "city", "date", "filename", "url", "content"}
    for hit in data["hits"]:
        assert required_hit_keys.issubset(hit.keys())


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
