from types import SimpleNamespace

from pipeline.extraction_service import reextract_catalog_content


def test_reextract_catalog_content_rejects_missing_catalog():
    result = reextract_catalog_content(None, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"error": "Catalog not found"}


def test_reextract_catalog_content_rejects_missing_location():
    catalog = SimpleNamespace(
        id=41,
        location=None,
        url=None,
        content=None,
        content_hash=None,
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"error": "Catalog has no file location"}
    assert catalog.extraction_status == "pending"
    assert catalog.extraction_error == "Catalog has no file location"
    assert catalog.extraction_attempt_count == 1


def test_reextract_catalog_content_rejects_unsafe_path(mocker):
    catalog = SimpleNamespace(
        id=41,
        location="/tmp/agenda.pdf",
        url=None,
        content=None,
        content_hash=None,
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )
    mocker.patch("pipeline.extraction_service._is_safe_catalog_path", return_value=False)

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"error": "Unsafe file path"}
    assert catalog.extraction_status == "pending"
    assert catalog.extraction_error == "Unsafe file path"
    assert catalog.extraction_attempt_count == 1


def test_reextract_catalog_content_rejects_missing_file(mocker):
    catalog = SimpleNamespace(
        id=41,
        location="/tmp/agenda.pdf",
        url=None,
        content=None,
        content_hash=None,
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )
    mocker.patch("pipeline.extraction_service._is_safe_catalog_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=False)

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"error": "File not found on disk"}
    assert catalog.extraction_status == "pending"
    assert catalog.extraction_error == "File not found on disk"
    assert catalog.extraction_attempt_count == 1


def test_reextract_catalog_content_returns_cached_when_existing_text_is_good_enough(mocker):
    catalog = SimpleNamespace(
        id=44,
        location="/tmp/agenda.txt",
        url=None,
        content="This extracted meeting text is long enough to keep.",
        content_hash="existing-hash",
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )
    mocker.patch("pipeline.extraction_service._is_safe_catalog_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=True)

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"status": "cached", "catalog_id": 44, "chars": len(catalog.content)}
    assert catalog.extraction_status == "complete"


def test_reextract_catalog_content_rejects_empty_extraction(mocker):
    catalog = SimpleNamespace(
        id=45,
        location="/tmp/agenda.pdf",
        url=None,
        content=None,
        content_hash=None,
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )
    mocker.patch("pipeline.extraction_service._is_safe_catalog_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=True)
    mocker.patch("pipeline.extraction_service._extract_catalog_text", return_value="")

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=False, min_chars=10)

    assert result == {"error": "Extraction returned empty text"}
    assert catalog.extraction_status == "pending"
    assert catalog.extraction_error == "Extraction returned empty text"
    assert catalog.extraction_attempt_count == 1


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

    mocker.patch("pipeline.extraction_service._is_safe_catalog_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=True)
    mocker.patch(
        "pipeline.extraction_service._extract_catalog_text",
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

    mocker.patch("pipeline.extraction_service._is_safe_catalog_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=True)
    mocker.patch(
        "pipeline.extraction_service._extract_catalog_text",
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


def test_reextract_catalog_content_updates_catalog_after_success(mocker):
    catalog = SimpleNamespace(
        id=46,
        location="/tmp/agenda.pdf",
        url="https://example.com/agenda.pdf",
        content=None,
        content_hash=None,
        extraction_attempt_count=0,
        extraction_status="pending",
        extraction_error=None,
        extraction_attempted_at=None,
    )
    mocker.patch("pipeline.extraction_service._is_safe_catalog_path", return_value=True)
    mocker.patch("pipeline.extraction_service.os.path.exists", return_value=True)
    mocker.patch("pipeline.extraction_service._extract_catalog_text", return_value="Raw extracted text")
    mocker.patch("pipeline.extraction_service._postprocess_catalog_text", return_value="Clean extracted text")

    result = reextract_catalog_content(catalog, force=False, ocr_fallback=True, min_chars=10)

    assert result["status"] == "updated"
    assert result["catalog_id"] == 46
    assert result["chars"] == len("Clean extracted text")
    assert result["ocr_fallback"] is True
    assert result["content_hash"] == catalog.content_hash
    assert catalog.content == "Clean extracted text"
    assert catalog.extraction_status == "complete"
    assert catalog.extraction_error is None
