from types import SimpleNamespace

from pipeline.laserfiche_error_pages import (
    DOCUMENT_SHAPE_FAMILY,
    LASERFICHE_FAMILY,
    LASERFICHE_ERROR_PAGE_REASON,
    LASERFICHE_LOADING_SHELL_REASON,
    SINGLE_ITEM_STAFF_REPORT_REASON,
    catalog_has_laserfiche_error_content,
    catalog_has_laserfiche_loading_shell_content,
    catalog_has_poisoned_laserfiche_content,
    classify_catalog_bad_content,
    classify_text_bad_content,
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
    classification = classify_text_bad_content(text)
    assert classification is not None
    assert classification.family == LASERFICHE_FAMILY
    assert classification.reason == LASERFICHE_LOADING_SHELL_REASON


def test_is_laserfiche_loading_shell_text_does_not_match_real_agenda_text():
    text = """
    CITY COUNCIL AGENDA
    1. CALL TO ORDER
    2. PUBLIC COMMENT
    3. CONSENT CALENDAR
    4. ADJOURNMENT
    """

    assert is_laserfiche_loading_shell_text(text) is False
    assert classify_text_bad_content(text) is None


def test_classify_text_bad_content_detects_single_item_staff_report_shape():
    text = """
    CITY OF SAN MATEO
    Agenda Report
    Agenda Number: 8
    Section Name: NEW BUSINESS
    TO: City Council
    FROM: Alex Khojikian, City Manager
    SUBJECT: Boards and Commissions Vacancy Process
    RECOMMENDATION: Approve the revised vacancy process.
    """

    classification = classify_text_bad_content(
        text,
        document_category="agenda",
        include_document_shape=True,
        has_viable_structured_source=False,
    )

    assert classification is not None
    assert classification.family == DOCUMENT_SHAPE_FAMILY
    assert classification.reason == SINGLE_ITEM_STAFF_REPORT_REASON


def test_classify_text_bad_content_skips_single_item_staff_report_when_structured_source_exists():
    text = """
    CITY OF SAN MATEO
    Administrative Report
    Agenda Number: 26
    TO: City Council
    FROM: City Manager
    SUBJECT: Burial Costs
    RECOMMENDATION: Adopt a Resolution.
    """

    classification = classify_text_bad_content(
        text,
        document_category="agenda",
        include_document_shape=True,
        has_viable_structured_source=True,
    )

    assert classification is None


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

    classification = classify_catalog_bad_content(polluted)
    assert classification is not None
    assert classification.family == LASERFICHE_FAMILY
    assert classification.reason == LASERFICHE_ERROR_PAGE_REASON
    assert catalog_has_laserfiche_error_content(polluted) is True
    assert catalog_has_poisoned_laserfiche_content(polluted) is True
    assert detect_laserfiche_bad_content_reason(polluted) == LASERFICHE_ERROR_PAGE_REASON
    assert catalog_has_laserfiche_error_content(wrong_extension) is False
    assert classify_catalog_bad_content(wrong_extension) is None


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

    classification = classify_catalog_bad_content(polluted)
    assert classification is not None
    assert classification.family == LASERFICHE_FAMILY
    assert classification.reason == LASERFICHE_LOADING_SHELL_REASON
    assert catalog_has_laserfiche_loading_shell_content(polluted) is True
    assert catalog_has_poisoned_laserfiche_content(polluted) is True
    assert detect_laserfiche_bad_content_reason(polluted) == LASERFICHE_LOADING_SHELL_REASON
    assert catalog_has_laserfiche_loading_shell_content(wrong_url) is False
    assert classify_catalog_bad_content(wrong_url) is None
