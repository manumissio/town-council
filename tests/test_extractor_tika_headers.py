import os


def test_extractor_includes_optional_pdfbox_spacing_headers_when_configured(mocker, tmp_path):
    from pipeline import extractor

    fake_pdf = tmp_path / "sample.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    mocker.patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=False)
    mocker.patch.object(extractor, "TIKA_PDF_SPACING_TOLERANCE", "2.5")
    mocker.patch.object(extractor, "TIKA_PDF_AVG_CHAR_TOLERANCE", "1.5")

    parser_mock = mocker.patch("pipeline.extractor.parser.from_file")
    parser_mock.return_value = {"content": "<div class=\"page\">Page text</div>"}

    out = extractor.extract_text(str(fake_pdf))
    assert "Page text" in out
    headers = parser_mock.call_args.kwargs["headers"]
    assert headers["X-Tika-PDFspacingTolerance"] == "2.5"
    assert headers["X-Tika-PDFaverageCharTolerance"] == "1.5"


def test_extractor_omits_optional_pdfbox_spacing_headers_by_default(mocker, tmp_path):
    from pipeline import extractor

    fake_pdf = tmp_path / "sample.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    mocker.patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=False)
    mocker.patch.object(extractor, "TIKA_PDF_SPACING_TOLERANCE", "")
    mocker.patch.object(extractor, "TIKA_PDF_AVG_CHAR_TOLERANCE", "")

    parser_mock = mocker.patch("pipeline.extractor.parser.from_file")
    parser_mock.return_value = {"content": "<div class=\"page\">Page text</div>"}

    out = extractor.extract_text(str(fake_pdf))
    assert "Page text" in out
    headers = parser_mock.call_args.kwargs["headers"]
    assert "X-Tika-PDFspacingTolerance" not in headers
    assert "X-Tika-PDFaverageCharTolerance" not in headers
