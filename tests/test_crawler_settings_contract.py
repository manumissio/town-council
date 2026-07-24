import subprocess
import sys
from pathlib import Path


TOWN_COUNCIL_USER_AGENT = "TownCouncilBot/1.0 (+https://github.com/manumissio/town-council)"
SCRAPY_PROJECT_DIR = Path("council_crawler")
SCRAPY_SETTINGS_TIMEOUT_SECONDS = 10


def _scrapy_setting(setting_name: str) -> str:
    completed_settings_command = subprocess.run(
        [sys.executable, "-m", "scrapy", "settings", "--get", setting_name],
        cwd=SCRAPY_PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
        timeout=SCRAPY_SETTINGS_TIMEOUT_SECONDS,
    )
    return completed_settings_command.stdout.strip()


def test_crawler_identifies_town_council_and_preserves_politeness() -> None:
    assert _scrapy_setting("USER_AGENT") == TOWN_COUNCIL_USER_AGENT
    assert _scrapy_setting("ROBOTSTXT_OBEY") == "True"
    assert _scrapy_setting("DOWNLOAD_DELAY") == "2"
