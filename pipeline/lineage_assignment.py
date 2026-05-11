from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pipeline.models import Catalog


@dataclass(frozen=True)
class LineageMutationSummary:
    merge_count: int
    updated_count: int


def assign_lineage_components(
    catalogs_by_id: dict[int, Catalog],
    adjacency: dict[int, set[int]],
    components: list[list[int]],
    *,
    updated_at: datetime,
) -> LineageMutationSummary:
    merge_count = 0
    updated_count = 0
    for component in components:
        if component_merges_prior_lineages(catalogs_by_id, component):
            merge_count += 1
        updated_count += assign_lineage_component(
            catalogs_by_id,
            adjacency,
            component,
            updated_at=updated_at,
        )
    return LineageMutationSummary(merge_count=merge_count, updated_count=updated_count)


def component_merges_prior_lineages(catalogs_by_id: dict[int, Catalog], component: list[int]) -> bool:
    prior_lineage_ids = {
        (catalogs_by_id[catalog_id].lineage_id or "").strip()
        for catalog_id in component
        if (catalogs_by_id[catalog_id].lineage_id or "").strip()
    }
    return len(prior_lineage_ids) > 1


def assign_lineage_component(
    catalogs_by_id: dict[int, Catalog],
    adjacency: dict[int, set[int]],
    component: list[int],
    *,
    updated_at: datetime,
) -> int:
    lineage_id = f"lin-{component[0]}"
    updated_count = 0
    for catalog_id in component:
        confidence = compute_lineage_confidence(
            component_size=len(component),
            degree=len(adjacency.get(catalog_id, set())),
        )
        if update_catalog_lineage(
            catalogs_by_id[catalog_id],
            lineage_id=lineage_id,
            confidence=confidence,
            updated_at=updated_at,
        ):
            updated_count += 1
    return updated_count


def compute_lineage_confidence(*, component_size: int, degree: int) -> float:
    if component_size <= 1:
        return 0.2
    confidence = min(1.0, 0.3 + 0.2 * min(degree, 3) + 0.1 * min(component_size - 1, 5))
    return round(float(confidence), 3)


def update_catalog_lineage(
    catalog: Catalog,
    *,
    lineage_id: str,
    confidence: float,
    updated_at: datetime,
) -> bool:
    confidence_changed = catalog.lineage_confidence is None or abs(float(catalog.lineage_confidence) - confidence) > 1e-9
    if catalog.lineage_id == lineage_id and not confidence_changed:
        return False
    catalog.lineage_id = lineage_id
    catalog.lineage_confidence = confidence
    catalog.lineage_updated_at = updated_at
    return True
