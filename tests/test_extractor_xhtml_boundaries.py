import json
import logging
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from pipeline import extractor
from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline


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


@pytest.mark.parametrize("markup", [
    "<ul><li>1. Approve contract</li><li>2. Adopt budget</li></ul>",
    "<table><tr><td>1.</td><td>Approve contract</td></tr><tr><td>2.</td><td>Adopt budget</td></tr></table>",
    "<table><tr><th>1.</th><td>Approve contract</td></tr><tr><th>2.</th><td>Adopt budget</td></tr></table>",
    "<h2>1. Approve contract</h2><h2>2. Adopt budget</h2>",
])
def test_xhtml_item_boundaries_survive_into_agenda_extraction(markup: str) -> None:
    extracted = extractor.inject_page_markers([markup], mode="formfeed")
    agenda_items = run_agenda_extraction_pipeline(
        text=extracted,
        raw_provider_content=None,
        mode="balanced",
        logger=logging.getLogger(__name__),
    )

    assert [agenda_item["title"] for agenda_item in agenda_items] == ["Approve contract", "Adopt budget"]
