from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Final, TypeAlias, TypedDict


JsonPayload: TypeAlias = dict[str, Any]  # JSON sidecars can contain nested primitive/list/dict values.
OrmSession: TypeAlias = Any  # SQLAlchemy sessions and test stubs share dynamic query methods.

MANIFEST_PACKAGE_SCHEMA_VERSION: Final = 1
PHASE_EXTRACT: Final = "extract"
PHASE_SEGMENT: Final = "segment"
PHASE_SUMMARY: Final = "summary"
PHASE_ENTITY: Final = "entity"
PHASE_ORG: Final = "org"
PHASE_PEOPLE: Final = "people"
PROFILE_MANIFEST_PHASES: Final = (
    PHASE_EXTRACT,
    PHASE_SEGMENT,
    PHASE_SUMMARY,
    PHASE_ENTITY,
    PHASE_ORG,
    PHASE_PEOPLE,
)
DEFAULT_PHASE_QUOTAS: Final[dict[str, int]] = {
    PHASE_EXTRACT: 8,
    PHASE_SEGMENT: 6,
    PHASE_SUMMARY: 6,
    PHASE_ENTITY: 4,
    PHASE_ORG: 2,
    PHASE_PEOPLE: 4,
}


class ManifestCandidate(TypedDict, total=False):
    catalog_id: int
    event_id: int
    reset_names: list[str]


class AppliedPreconditioningCounts(TypedDict):
    deleted_agenda_items: int
    cleared_segment_catalogs: int
    cleared_summary_catalogs: int
    cleared_entity_catalogs: int
    cleared_org_events: int
    deleted_people: int


SessionFactory: TypeAlias = Callable[[], AbstractContextManager[OrmSession]]
CandidateLoader: TypeAlias = Callable[[OrmSession], list[ManifestCandidate]]
