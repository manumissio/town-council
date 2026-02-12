from pipeline.agenda_crosscheck import _extract_text_lines_from_html


def test_extract_text_lines_handles_malformed_script_end_tag():
    html = """
    <html><body>
      <script>
        alert("xss");
      </script >
      <div>2. Budget Hearing</div>
    </body></html>
    """
    lines = _extract_text_lines_from_html(html)
    joined = " ".join(lines).lower()
    assert "alert(" not in joined
    assert "2. budget hearing" in joined


def test_extract_text_lines_is_deterministic_for_broken_html():
    html = "<div>3. Public Comment<li>Unclosed item<div>4. Consent Calendar"
    first = _extract_text_lines_from_html(html)
    second = _extract_text_lines_from_html(html)
    assert first == second
