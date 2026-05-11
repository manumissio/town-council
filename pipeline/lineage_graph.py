from __future__ import annotations

from collections.abc import Iterable, Sequence

from pipeline.models import Catalog


def related_ids_as_int_set(values: Iterable[object] | None) -> set[int]:
    related_ids: set[int] = set()
    for raw_related_id in values or []:
        try:
            related_ids.add(int(raw_related_id))
        except (TypeError, ValueError):
            continue
    return related_ids


def build_related_catalog_map(catalogs: Sequence[Catalog]) -> dict[int, set[int]]:
    return {int(catalog.id): related_ids_as_int_set(catalog.related_ids or []) for catalog in catalogs}


def build_lineage_adjacency(
    catalog_ids: set[int],
    related_catalog_ids: dict[int, set[int]],
    *,
    min_edge_confidence: float,
    require_mutual_edges: bool,
) -> dict[int, set[int]]:
    adjacency: dict[int, set[int]] = {catalog_id: set() for catalog_id in catalog_ids}
    for catalog_id, neighbor_ids in related_catalog_ids.items():
        add_confident_edges(
            adjacency,
            catalog_id=catalog_id,
            neighbor_ids=neighbor_ids,
            catalog_ids=catalog_ids,
            related_catalog_ids=related_catalog_ids,
            min_edge_confidence=min_edge_confidence,
            require_mutual_edges=require_mutual_edges,
        )
    return adjacency


def add_confident_edges(
    adjacency: dict[int, set[int]],
    *,
    catalog_id: int,
    neighbor_ids: set[int],
    catalog_ids: set[int],
    related_catalog_ids: dict[int, set[int]],
    min_edge_confidence: float,
    require_mutual_edges: bool,
) -> None:
    for neighbor_id in neighbor_ids:
        if should_link_catalogs(
            catalog_id,
            neighbor_id,
            catalog_ids=catalog_ids,
            related_catalog_ids=related_catalog_ids,
            min_edge_confidence=min_edge_confidence,
            require_mutual_edges=require_mutual_edges,
        ):
            adjacency[catalog_id].add(neighbor_id)
            adjacency[neighbor_id].add(catalog_id)


def should_link_catalogs(
    catalog_id: int,
    neighbor_id: int,
    *,
    catalog_ids: set[int],
    related_catalog_ids: dict[int, set[int]],
    min_edge_confidence: float,
    require_mutual_edges: bool,
) -> bool:
    if neighbor_id not in catalog_ids:
        return False
    is_mutual = catalog_id in related_catalog_ids.get(neighbor_id, set())
    if require_mutual_edges and not is_mutual:
        return False
    edge_confidence = 1.0 if is_mutual else 0.5
    return edge_confidence >= min_edge_confidence


def find_lineage_components(catalog_ids: set[int], adjacency: dict[int, set[int]]) -> list[list[int]]:
    seen: set[int] = set()
    components: list[list[int]] = []
    for catalog_id in sorted(catalog_ids):
        if catalog_id in seen:
            continue
        components.append(walk_lineage_component(catalog_id, adjacency, seen))
    return components


def walk_lineage_component(
    start_catalog_id: int,
    adjacency: dict[int, set[int]],
    seen: set[int],
) -> list[int]:
    stack = [start_catalog_id]
    component: list[int] = []
    while stack:
        catalog_id = stack.pop()
        if catalog_id in seen:
            continue
        seen.add(catalog_id)
        component.append(catalog_id)
        stack.extend(neighbor_id for neighbor_id in sorted(adjacency.get(catalog_id, set()), reverse=True) if neighbor_id not in seen)
    return sorted(component)
