from pathlib import Path
from runpy import run_path


TOWN_COUNCIL_USER_AGENT = "TownCouncilBot/1.0 (+https://github.com/manumissio/town-council)"
CRAWLER_SETTINGS_PATH = Path("council_crawler/council_crawler/settings.py")


def test_crawler_identifies_town_council_and_preserves_politeness() -> None:
    crawler_settings = run_path(str(CRAWLER_SETTINGS_PATH))

    assert crawler_settings["USER_AGENT"] == TOWN_COUNCIL_USER_AGENT
    assert crawler_settings["ROBOTSTXT_OBEY"] is True
    assert crawler_settings["DOWNLOAD_DELAY"] == 2
