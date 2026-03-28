from types import SimpleNamespace

from pipeline.laserfiche_error_pages import (
    LASERFICHE_ERROR_PAGE_REASON,
    LASERFICHE_LOADING_SHELL_REASON,
    catalog_has_laserfiche_error_content,
    catalog_has_laserfiche_loading_shell_content,
    catalog_has_poisoned_laserfiche_content,
    detect_laserfiche_bad_content_reason,
    detect_laserfiche_bad_text_reason,
    is_laserfiche_error_text,
    is_laserfiche_loading_shell_text,
)


def test_is_laserfiche_error_text_matches_known_error_page_copy():
    text = """
    Error
    The system has encountered an error and could not complete your request.
    If the problem persists, please contact the site administrator.
    """

    assert is_laserfiche_error_text(text) is True


def test_is_laserfiche_error_text_does_not_match_real_agenda_text():
    text = """
    CITY COUNCIL AGENDA
    1. CALL TO ORDER
    2. PUBLIC COMMENT
    3. CONSENT CALENDAR
    4. ADJOURNMENT
    """

    assert is_laserfiche_error_text(text) is False


def test_is_laserfiche_loading_shell_text_matches_known_shell_copy():
    text = """
    [PAGE 1] Loading...
    The URL can be used to link to this page
    Your browser does not support the video tag.
    """

    assert is_laserfiche_loading_shell_text(text) is True
    assert detect_laserfiche_bad_text_reason(text) == LASERFICHE_LOADING_SHELL_REASON


def test_is_laserfiche_loading_shell_text_does_not_match_real_agenda_text():
    text = """
    CITY COUNCIL AGENDA
    1. CALL TO ORDER
    2. PUBLIC COMMENT
    3. CONSENT CALENDAR
    4. ADJOURNMENT
    """

    assert is_laserfiche_loading_shell_text(text) is False


def test_catalog_has_laserfiche_error_content_requires_matching_shape():
    polluted = SimpleNamespace(
        location="/tmp/agenda.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=123",
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
    )
    wrong_extension = SimpleNamespace(
        location="/tmp/agenda.pdf",
        url=polluted.url,
        content=polluted.content,
    )

    assert catalog_has_laserfiche_error_content(polluted) is True
    assert catalog_has_poisoned_laserfiche_content(polluted) is True
    assert detect_laserfiche_bad_content_reason(polluted) == LASERFICHE_ERROR_PAGE_REASON
    assert catalog_has_laserfiche_error_content(wrong_extension) is False


def test_catalog_has_laserfiche_loading_shell_content_requires_matching_shape():
    polluted = SimpleNamespace(
        location="/tmp/agenda.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=123",
        content=(
            "[PAGE 1] Loading... The URL can be used to link to this page "
            "Your browser does not support the video tag."
        ),
    )
    wrong_url = SimpleNamespace(
        location=polluted.location,
        url="https://example.com/agenda.html",
        content=polluted.content,
    )

    assert catalog_has_laserfiche_loading_shell_content(polluted) is True
    assert catalog_has_poisoned_laserfiche_content(polluted) is True
    assert detect_laserfiche_bad_content_reason(polluted) == LASERFICHE_LOADING_SHELL_REASON
    assert catalog_has_laserfiche_loading_shell_content(wrong_url) is False
