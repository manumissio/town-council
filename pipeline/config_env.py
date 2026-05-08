from __future__ import annotations

import os
from collections.abc import Collection


TRUE_ENV_VALUES = frozenset({"1", "true", "yes"})


def env_bool(name: str, default: bool) -> bool:
    default_text = "true" if default else "false"
    return os.getenv(name, default_text).strip().lower() in TRUE_ENV_VALUES


def env_int(name: str, default: int | str) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str, default: float | str) -> float:
    return float(os.getenv(name, str(default)))


def env_raw(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_stripped(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def env_lower(name: str, default: str) -> str:
    return env_stripped(name, default).lower()


def env_nonempty_stripped(name: str, default: str) -> str:
    return env_stripped(name, default) or default


def env_nonempty_lower(name: str, default: str) -> str:
    return env_lower(name, default) or default


def env_choice(name: str, default: str, allowed_values: Collection[str]) -> str:
    value = env_nonempty_lower(name, default)
    if value in allowed_values:
        return value
    return default
