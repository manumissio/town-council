from pathlib import Path


def test_onboarding_wave_script_contains_expected_waves():
    path = Path("scripts/onboard_city_wave.sh")
    text = path.read_text(encoding="utf-8")

    for city in (
        "fremont",
        "hayward",
        "san_mateo",
        "sunnyvale",
        "san_leandro",
        "mtn_view",
        "moraga",
        "belmont",
    ):
        assert city in text

    for city in (
        "orinda",
        "brisbane",
        "danville",
        "los_gatos",
        "los_altos",
        "palo_alto",
        "san_bruno",
        "east_palo_alto",
        "santa_clara",
    ):
        assert city in text

    assert "crawl success >=95% over 3 runs" in text
    assert "non-empty extraction >=90%" in text
    assert "segmentation complete/empty >=95%" in text
    assert "scripts/segment_city_corpus.py --city" in text
    assert "scripts/check_city_crawl_evidence.py" in text
    assert "crawler_empty" in text
    assert "PIPELINE_ONBOARDING_CITY" in text
    assert "PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE=5" in text
    assert "PIPELINE_ONBOARDING_MAX_WORKERS=1" in text
    assert "TIKA_OCR_FALLBACK_ENABLED=false" in text
