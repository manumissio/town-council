import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FORMATTER_PATH = REPO_ROOT / "frontend" / "lib" / "textFormatter.js"


def _call_formatter(function_name: str, text: str):
    js = (
        "const f=require(process.argv[1]);"
        "const fn=process.argv[2];"
        "const input=process.argv[3];"
        "const out=f[fn](input);"
        "process.stdout.write(JSON.stringify(out));"
    )
    proc = subprocess.run(
        ["node", "-e", js, str(FORMATTER_PATH), function_name, text],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_normalize_whitespace_collapses_blank_lines_and_spaces():
    raw = "Line one   \n\n\n   Line   two\n\n"
    out = _call_formatter("normalizeWhitespace", raw)
    assert out == "Line one\n\nLine two"


def test_split_by_page_markers_creates_sections():
    raw = "[PAGE 1]\nHello world\n\n[PAGE 2]\nSecond page"
    out = _call_formatter("splitByPageMarkers", raw)
    assert len(out) == 2
    assert out[0]["pageNumber"] == 1
    assert out[1]["pageNumber"] == 2
    assert out[1]["lines"] == ["Second page"]


def test_render_formatted_text_converts_markers_to_headers():
    raw = "[PAGE 1]\nAgenda line\n\n- Item A\n- Item B"
    html = _call_formatter("renderFormattedExtractedText", raw)
    assert "Page 1" in html
    assert "[PAGE 1]" not in html
    assert "<ul" in html
    assert "Item A" in html


def test_render_formatted_text_handles_empty_input():
    html = _call_formatter("renderFormattedExtractedText", "")
    assert html == ""
