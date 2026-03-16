from pipeline.lexicon import (
    contains_shared_agenda_boilerplate_phrase,
    is_agenda_boilerplate_title,
    is_contact_or_letterhead_noise,
    is_name_like_title,
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


def test_shared_agenda_boilerplate_phrase_detection():
    assert contains_shared_agenda_boilerplate_phrase("In witness whereof the official seal shall be affixed forthwith")
    assert contains_shared_agenda_boilerplate_phrase("COMMUNICATION ACCESS INFORMATION")
    assert not contains_shared_agenda_boilerplate_phrase("Adopt budget ordinance")


def test_agenda_boilerplate_title_detection_from_single_source():
    assert is_agenda_boilerplate_title("COMMUNICATION ACCESS INFORMATION:")
    assert is_agenda_boilerplate_title("Agendas and agenda reports may be accessed via the Internet at http://example.com")
    assert not is_agenda_boilerplate_title("Budget Amendment")


def test_name_like_title_detection_from_single_source():
    assert is_name_like_title("Leslie Sakai")
    assert not is_name_like_title("Budget Amendment")
    assert not is_name_like_title("Kirk McCarthy (2)")
