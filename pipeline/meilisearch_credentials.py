DEVELOPMENT_APP_ENV = "dev"
DEVELOPMENT_MEILI_SEARCH_KEY = "masterKey"
MISSING_MEILI_SEARCH_KEY_MESSAGE = "MEILI_SEARCH_KEY must be set when APP_ENV is not dev."
DEVELOPMENT_MEILI_SEARCH_KEY_MESSAGE = (
    "MEILI_SEARCH_KEY must not use the development fallback when APP_ENV is not dev."
)
UNSAFE_MEILI_SEARCH_KEY_MESSAGE = (
    "MEILI_SEARCH_KEY must contain printable ASCII characters without leading or trailing whitespace."
)
MEILI_SEARCH_KEY_FALLBACK_WARNING = "Meilisearch reader is using the development fallback key."


def resolve_meilisearch_reader_key(app_env: str, search_key: str) -> str:
    normalized_app_env = app_env.strip().lower()
    normalized_search_key = search_key.strip()
    if not normalized_search_key:
        if normalized_app_env == DEVELOPMENT_APP_ENV:
            return DEVELOPMENT_MEILI_SEARCH_KEY
        raise RuntimeError(MISSING_MEILI_SEARCH_KEY_MESSAGE)
    if (
        normalized_app_env != DEVELOPMENT_APP_ENV
        and normalized_search_key == DEVELOPMENT_MEILI_SEARCH_KEY
    ):
        raise RuntimeError(DEVELOPMENT_MEILI_SEARCH_KEY_MESSAGE)
    if (
        not search_key.isascii()
        or not search_key.isprintable()
        or search_key != normalized_search_key
    ):
        raise RuntimeError(UNSAFE_MEILI_SEARCH_KEY_MESSAGE)
    return search_key
