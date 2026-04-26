from meilisearch.errors import MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError


REINDEX_FAILURE_EXCEPTIONS = (
    MeilisearchCommunicationError,
    MeilisearchTimeoutError,
    MeilisearchError,
    RuntimeError,
    OSError,
    ConnectionError,
    TimeoutError,
    ValueError,
)
