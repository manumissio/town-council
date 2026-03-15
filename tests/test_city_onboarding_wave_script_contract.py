from pathlib import Path


def test_onboarding_wave_script_uses_rollout_registry():
    path = Path("scripts/onboard_city_wave.sh")
    text = path.read_text(encoding="utf-8")

    assert "city_metadata/city_rollout_registry.csv" in text
    assert "scripts/rollout_registry.py --wave" in text
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
