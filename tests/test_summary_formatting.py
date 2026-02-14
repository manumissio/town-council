import sys
from unittest.mock import MagicMock

# Prevent importing llama-cpp during unit tests.
sys.modules["llama_cpp"] = MagicMock()

from pipeline.llm import _normalize_summary_output_to_bluf


def test_normalize_summary_strips_markdown_and_enforces_bluf():
    raw = """Here's a summary of the meeting minutes:
* **Agenda:** Teleconference meeting via Zoom (register in advance)
* **Action:** Approved a budget amendment.
* **Vote:** All Ayes.
"""
    out = _normalize_summary_output_to_bluf(raw, source_text="Budget amendment. Vote: All Ayes.")

    assert out.startswith("BLUF:")
    assert "*" not in out
    assert "**" not in out
    # Teleconference boilerplate should be removed.
    lowered = out.lower()
    assert "zoom" not in lowered
    assert "teleconference" not in lowered

    # Bullet lines should use "- " prefix.
    bullet_lines = [ln for ln in out.splitlines() if ln.startswith("- ")]
    assert len(bullet_lines) >= 2


def test_normalize_summary_limits_bullets_to_seven():
    raw = "\n".join(["BLUF: Main takeaway."] + [f"- Detail {i}." for i in range(1, 20)])
    out = _normalize_summary_output_to_bluf(raw, source_text="Some source text.")

    bullet_lines = [ln for ln in out.splitlines() if ln.startswith("- ")]
    assert len(bullet_lines) <= 7


def test_normalize_summary_suppresses_attendance_lines():
    raw = """BLUF: Committee discussed agenda items.
- Join by phone: (510) 555-1234
- Meeting ID 123 456 789
- Budget amendment approved.
- Public safety update received.
"""
    out = _normalize_summary_output_to_bluf(raw, source_text="Budget amendment approved. Public safety update received.")
    lowered = out.lower()
    assert "join by phone" not in lowered
    assert "meeting id" not in lowered
    assert "budget amendment" in lowered

