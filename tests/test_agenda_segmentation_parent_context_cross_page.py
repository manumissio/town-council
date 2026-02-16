from unittest.mock import MagicMock


def test_parent_context_persists_across_pages_for_subitems():
    from pipeline.llm import LocalAI

    LocalAI._instance = None
    ai = LocalAI()
    ai.llm = MagicMock()
    ai.llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    text = """
    [PAGE 2]
    1. Subject: Downtown Streetscape Contract Package
    Recommendation: Conduct a public hearing and take the following action:

    [PAGE 3]
    A. Contract expansion for traffic controls
    B. Utility relocation allowance
    2. Subject: Annual Work Program
    Recommended Action: Receive annual work program report.
    """

    items = ai.extract_agenda(text)
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)
    assert any("downtown streetscape contract package" in t for t in titles)
    assert any("annual work program" in t for t in titles)
    assert "contract expansion for traffic controls" not in joined
    assert "utility relocation allowance" not in joined
