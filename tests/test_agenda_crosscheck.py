from pipeline.agenda_crosscheck import (
    _extract_text_lines_from_html,
    parse_eagenda_items_from_html,
    merge_ai_with_eagenda,
)


def test_parse_eagenda_items_from_html_extracts_numbered_sections():
    html = """
    <html><body>
      <table>
        <tr><td>1. Public Employee Appointments</td></tr>
        <tr><td>2. Budget Amendment for FY 2026</td></tr>
        <tr><td>3. Police Accountability Director Position</td></tr>
      </table>
    </body></html>
    """
    items = parse_eagenda_items_from_html(html)
    assert len(items) == 3
    assert items[0]["title"] == "Public Employee Appointments"
    assert items[1]["title"] == "Budget Amendment for FY 2026"


def test_merge_ai_with_eagenda_prefers_structured_html_when_rich():
    ai_items = [
        {"order": 1, "title": "Special Closed Meeting 10/03/11"},
        {"order": 2, "title": "state of emergency continues ..."},
    ]
    eagenda_items = [
        {"order": 1, "title": "Public Employee Appointments", "description": "eAgenda section 1"},
        {"order": 2, "title": "Budget Amendment for FY 2026", "description": "eAgenda section 2"},
        {"order": 3, "title": "Director of Police Accountability", "description": "eAgenda section 3"},
    ]

    merged = merge_ai_with_eagenda(ai_items, eagenda_items)
    assert len(merged) == 3
    assert merged[0]["title"] == "Public Employee Appointments"


def test_extract_text_lines_strips_script_style_and_noscript_content():
    html = """
    <html><body>
      <script>window.evil = 1;</script>
      <style>.hidden { display:none; }</style>
      <noscript>Fallback script message</noscript>
      <div>1. Safe Agenda Title</div>
    </body></html>
    """
    lines = _extract_text_lines_from_html(html)
    joined = " ".join(lines).lower()
    assert "evil" not in joined
    assert "hidden" not in joined
    assert "fallback script message" not in joined
    assert "1. safe agenda title" in joined
