from types import SimpleNamespace

from pipeline.extraction_service import reextract_catalog_content


def test_reextract_catalog_content_rejects_laserfiche_error_html(mocker):
    catalog = SimpleNamespace(
        id=42,
        location="/tmp/agenda.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=42",
        content=None,
        content_hash=None,
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )

    mocker.patch("pipeline.extraction_service.is_safe_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=True)
    mocker.patch(
        "pipeline.extraction_service.extract_text",
        return_value=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
    )

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"error": "laserfiche_error_page_detected"}
    assert catalog.content is None
    assert catalog.extraction_status == "pending"
    assert catalog.extraction_error == "laserfiche_error_page_detected"
    assert catalog.extraction_attempt_count == 1


def test_reextract_catalog_content_rejects_laserfiche_loading_shell_html(mocker):
    catalog = SimpleNamespace(
        id=43,
        location="/tmp/agenda.html",
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=43",
        content=None,
        content_hash=None,
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )

    mocker.patch("pipeline.extraction_service.is_safe_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=True)
    mocker.patch(
        "pipeline.extraction_service.extract_text",
        return_value=(
            "[PAGE 1] Loading... The URL can be used to link to this page "
            "Your browser does not support the video tag."
        ),
    )

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"error": "laserfiche_loading_shell_detected"}
    assert catalog.content is None
    assert catalog.extraction_status == "pending"
    assert catalog.extraction_error == "laserfiche_loading_shell_detected"
    assert catalog.extraction_attempt_count == 1
