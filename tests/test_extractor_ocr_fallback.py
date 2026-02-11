import os


def test_extractor_ocr_fallback_disabled_does_not_retry_with_ocr(mocker, tmp_path):
    """
    If OCR fallback is disabled, we should not call Tika with an OCR strategy even
    when the digital text layer is empty/short.
    """
    from pipeline import extractor

    fake_pdf = tmp_path / "scan.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    # Ensure the extractor considers the file path safe by pointing DATA_DIR at tmp_path.
    mocker.patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=False)
    mocker.patch.object(extractor, "TIKA_OCR_FALLBACK_ENABLED", False)

    parser_mock = mocker.patch("pipeline.extractor.parser.from_file")
    parser_mock.return_value = {"content": ""}  # digital layer empty

    text = extractor.extract_text(str(fake_pdf))
    assert text == ""

    # Only the first (no_ocr) strategy should be attempted.
    assert parser_mock.call_count == 3  # retries
    for _, kwargs in parser_mock.call_args_list:
        assert kwargs["headers"]["X-Tika-PDFOcrStrategy"] == "no_ocr"


def test_extractor_ocr_fallback_enabled_retries_with_ocr_when_text_is_too_short(mocker, tmp_path):
    """
    If OCR fallback is enabled and the digital text layer is too small, retry using OCR.
    """
    from pipeline import extractor

    fake_pdf = tmp_path / "scan.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    mocker.patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=False)
    mocker.patch.object(extractor, "TIKA_OCR_FALLBACK_ENABLED", True)
    mocker.patch.object(extractor, "TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR", 800)

    parser_mock = mocker.patch("pipeline.extractor.parser.from_file")
    # First pass (no_ocr): short content. Second pass (ocr_only): meaningful content.
    parser_mock.side_effect = [
        {"content": "short"},
        {"content": "<div class=\"page\">OCR page text</div>"},
    ]

    text = extractor.extract_text(str(fake_pdf))
    assert "OCR page text" in text

    assert parser_mock.call_count == 2
    first_kwargs = parser_mock.call_args_list[0].kwargs
    second_kwargs = parser_mock.call_args_list[1].kwargs
    assert first_kwargs["headers"]["X-Tika-PDFOcrStrategy"] == "no_ocr"
    assert second_kwargs["headers"]["X-Tika-PDFOcrStrategy"] == "ocr_only"
