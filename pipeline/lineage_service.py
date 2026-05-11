from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from pipeline.lineage_assignment import assign_lineage_components
from pipeline.lineage_graph import build_lineage_adjacency, build_related_catalog_map, find_lineage_components
from pipeline.models import Catalog


@dataclass
class LineageAssignmentResult:
    catalog_count: int
    component_count: int
    merge_count: int
    updated_count: int


def compute_lineage_assignments(
    db: Session,
    min_edge_confidence: float = 0.5,
    require_mutual_edges: bool = False,
) -> LineageAssignmentResult:
    """
    Compute deterministic meeting-level lineage groups from catalog.related_ids.

    We treat the related-id graph as undirected and assign lineage IDs using the
    minimum catalog ID in each connected component (lin-<min_id>), which keeps
    IDs stable and reproducible across reruns.
    """
    catalogs = db.query(Catalog).all()
    if not catalogs:
        return LineageAssignmentResult(catalog_count=0, component_count=0, merge_count=0, updated_count=0)

    catalogs_by_id = {int(catalog.id): catalog for catalog in catalogs}
    catalog_ids = set(catalogs_by_id)
    related_catalog_ids = build_related_catalog_map(catalogs)
    adjacency = build_lineage_adjacency(
        catalog_ids,
        related_catalog_ids,
        min_edge_confidence=min_edge_confidence,
        require_mutual_edges=require_mutual_edges,
    )
    components = find_lineage_components(catalog_ids, adjacency)
    mutation_summary = assign_lineage_components(
        catalogs_by_id,
        adjacency,
        components,
        updated_at=datetime.now(timezone.utc),
    )

    db.flush()
    return LineageAssignmentResult(
        catalog_count=len(catalogs),
        component_count=len(components),
        merge_count=mutation_summary.merge_count,
        updated_count=mutation_summary.updated_count,
    )
