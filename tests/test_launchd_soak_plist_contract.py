from pathlib import Path


def test_launchd_plist_contract():
    text = Path("ops/launchd/com.towncouncil.soak.daily.plist").read_text(encoding="utf-8")

    assert "com.towncouncil.soak.daily" in text
    assert "run_soak_day.sh" in text
    assert "collect_soak_metrics.py" in text
    assert "EnvironmentVariables" in text
    assert "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" in text
    assert "StartCalendarInterval" in text
    assert "<integer>19</integer>" in text
    assert "<integer>55</integer>" in text
    assert "/Users/dennisshah/GitHub/town-council/experiments/results/soak/launchd.out.log" in text
    assert "/Users/dennisshah/GitHub/town-council/experiments/results/soak/launchd.err.log" in text
