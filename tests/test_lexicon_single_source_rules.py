from pipeline.lexicon import (
    is_contact_or_letterhead_noise,
    is_procedural_title,
    is_trend_noise_topic,
    normalize_title_key,
)


def test_procedural_title_detection_from_single_source():
    assert is_procedural_title("Roll Call")
    assert is_procedural_title("approval of the minutes")
    assert not is_procedural_title("Approval of Contract Amendment")


def test_contact_noise_detection_from_single_source():
    assert is_contact_or_letterhead_noise("Phone: 555-111-2222", "")
    assert is_contact_or_letterhead_noise("From: Clerk Office", "")
    assert not is_contact_or_letterhead_noise("Adopt budget ordinance", "")


def test_trend_noise_topic():
    assert is_trend_noise_topic("Roll Call")
    assert not is_trend_noise_topic("Housing")


def test_title_key_normalization():
    assert normalize_title_key("Item 3:   Public Comment") == "public comment"
