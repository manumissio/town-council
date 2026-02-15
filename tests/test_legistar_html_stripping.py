from pipeline.agenda_legistar import strip_html_to_text


def test_strip_html_to_text_strips_tags_and_unescapes():
    raw = 'Subject: Discuss <em class="bg-yellow-200">Zoning</em> Laws &amp; Policy'
    assert strip_html_to_text(raw) == "Subject: Discuss Zoning Laws & Policy"


def test_strip_html_to_text_handles_none_and_whitespace():
    assert strip_html_to_text(None) == ""
    assert strip_html_to_text("  <b>Test</b>  ") == "Test"

