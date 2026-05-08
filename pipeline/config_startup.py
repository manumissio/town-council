from __future__ import annotations

from dataclasses import dataclass

from pipeline.config_env import env_bool, env_lower


@dataclass(frozen=True, slots=True)
class StartupConfig:
    startup_purge_derived: bool
    app_env: str
    startup_purge_allow_non_dev: bool


def load_startup_config() -> StartupConfig:
    return StartupConfig(
        startup_purge_derived=env_bool("STARTUP_PURGE_DERIVED", False),
        app_env=env_lower("APP_ENV", "dev"),
        startup_purge_allow_non_dev=env_bool("STARTUP_PURGE_ALLOW_NON_DEV", False),
    )
