from pathlib import Path


def test_launchd_plist_contract():
    text = Path("ops/launchd/com.towncouncil.soak.daily.plist").read_text(encoding="utf-8")

    assert "com.towncouncil.soak.daily" in text
    assert "run_soak_day.sh" in text
    assert "collect_soak_metrics.py" in text
    assert "StartCalendarInterval" in text
    assert "<integer>3</integer>" in text
    assert "<integer>0</integer>" in text

