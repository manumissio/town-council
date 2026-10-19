import json
from pathlib import Path

from pytest_mock import MockerFixture

from pipeline import extractor


def test_extraction_preserves_real_pages_from_tika_xhtml(mocker: MockerFixture, tmp_path: Path) -> None:
    source_pdf = tmp_path / "meeting.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 transport fixture")
    mocker.patch.dict("os.environ", {"DATA_DIR": str(tmp_path)})

    def tika_response(*arguments: object, **request_options: object) -> tuple[int, str]:
        content = "First page business\nSecond page business"
        if arguments[2] == "/rmeta/xml":
            content = '<div class="page"><p>First page business</p></div><div class="page"><p>Second page business</p></div>'
        return 200, json.dumps([{"X-TIKA:content": content}])

    mocker.patch("tika.tika.callServer", side_effect=tika_response)

    extracted = extractor.extract_text(str(source_pdf), ocr_fallback_enabled=False)

    assert "[PAGE 1]\nFirst page business" in extracted
    assert "[PAGE 2]\nSecond page business" in extracted


def test_xhtml_paragraphs_do_not_merge_when_tags_are_removed() -> None:
    extracted = extractor.inject_page_markers(
        ['<p>Approve the public works contract</p><p>Recommendation: Approve the contract.</p>'],
        mode="formfeed",
    )

    assert "contract\n" in extracted
    assert "contractRecommendation" not in extracted


def test_xhtml_entities_are_decoded_without_stripping_escaped_source_text() -> None:
    extracted = extractor.inject_page_markers(
        ["<p>Water &amp; Sewer Contract</p><p>Cost &lt; $250,000; use &lt;existing&gt; funds.</p>"],
        mode="formfeed",
    )

    assert "Water & Sewer Contract" in extracted
    assert "Cost < $250,000; use <existing> funds." in extracted
