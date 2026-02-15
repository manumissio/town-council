from pathlib import Path


def test_result_card_refreshes_derived_status_after_segmentation():
    """
    Regression: after agenda segmentation completes, the UI should refresh derived status so
    the "Not generated yet" badge clears without requiring a manual page refresh.
    """
    source = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")

    # Minimal (string-based) contract: agenda handler calls fetchDerivedStatus after success.
    assert "const handleGenerateAgenda" in source
    assert "fetchDerivedStatus();" in source

