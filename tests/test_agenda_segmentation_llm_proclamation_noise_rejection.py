from unittest.mock import MagicMock


def test_llm_path_rejects_proclamation_and_conduct_notice_lines():
    from pipeline.llm import LocalAI

    LocalAI._instance = None
    ai = LocalAI()

    class _FakeLLM:
        def __call__(self, prompt, max_tokens=0, temperature=0.0):
            return {
                "choices": [
                    {
                        "text": (
                            " In accordance with the authority in me vested, I do hereby call the Berkeley City Council in special "
                            "(Page 1) - In accordance with the authority in me vested, I do hereby call the Berkeley City Council in special session as follows:\n"
                            "ITEM 2: Pursuant to the City Council Rules of Procedure and State Law, the presiding officer may remove, or cause the "
                            "(Page 1) - Pursuant to the City Council Rules of Procedure and State Law, the presiding officer may remove, or cause the removal of, an individual for disrupting the meeting.\n"
                            "ITEM 3: 2026 City Council Referral Prioritization Results Using Re-Weighted Range Voting (RRV) "
                            "(Page 2) - Review the completed Re-Weighted Range Voting rankings and adopt a resolution."
                        )
                    }
                ]
            }

        def reset(self):
            return None

    ai.llm = _FakeLLM()
    items = ai.extract_agenda("dummy")
    titles = [it.get("title", "").lower() for it in items]
    joined = " ".join(titles)

    assert any("re-weighted range voting" in t for t in titles)
    assert "in accordance with the authority in me vested" not in joined
    assert "presiding officer may remove" not in joined
