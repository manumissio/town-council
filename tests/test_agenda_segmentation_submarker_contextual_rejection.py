from unittest.mock import MagicMock


def test_submarker_rejected_only_with_active_parent_context():
    from pipeline.llm import LocalAI

    LocalAI._instance = None
    ai = LocalAI()
    ai.llm = MagicMock()
    ai.llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    with_parent = """
    [PAGE 1]
    1. Subject: Regional Mobility Package
    Recommendation: Conduct a public hearing and take the following action:
    A. Contract amendment for corridor upgrades
    2. Subject: Tree Program Update
    """
    items_with_parent = ai.extract_agenda(with_parent)
    joined_with_parent = " ".join(it.get("title", "").lower() for it in items_with_parent)
    assert "contract amendment for corridor upgrades" not in joined_with_parent

    LocalAI._instance = None
    ai2 = LocalAI()
    ai2.llm = MagicMock()
    ai2.llm.return_value = {"choices": [{"text": "No parseable agenda output"}]}

    without_parent = """
    [PAGE 1]
    A. Regional Transit Agreement Update
    Recommended Action: Authorize the City Manager to execute agreement amendments.
    """
    items_without_parent = ai2.extract_agenda(without_parent)
    joined_without_parent = " ".join(it.get("title", "").lower() for it in items_without_parent)
    assert "regional transit agreement update" in joined_without_parent
