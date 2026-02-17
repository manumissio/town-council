from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from pipeline.models import Catalog


@dataclass
class LineageAssignmentResult:
    catalog_count: int
    component_count: int
    merge_count: int
    updated_count: int


def _as_int_set(values: Iterable) -> set[int]:
    out: set[int] = set()
    for v in values or []:
        try:
            out.add(int(v))
        except Exception:
            continue
    return out


def compute_lineage_assignments(
    db,
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

    existing_by_id = {int(c.id): c for c in catalogs}
    related_map = {int(c.id): _as_int_set(c.related_ids or []) for c in catalogs}

    adjacency: dict[int, set[int]] = {cid: set() for cid in existing_by_id.keys()}
    for cid, neighbors in related_map.items():
        for nid in neighbors:
            if nid not in existing_by_id:
                continue
            is_mutual = cid in related_map.get(nid, set())
            edge_conf = 1.0 if is_mutual else 0.5
            if require_mutual_edges and not is_mutual:
                continue
            if edge_conf < min_edge_confidence:
                continue
            adjacency[cid].add(nid)
            adjacency[nid].add(cid)

    seen: set[int] = set()
    components: list[list[int]] = []
    for cid in sorted(existing_by_id.keys()):
        if cid in seen:
            continue
        stack = [cid]
        comp: list[int] = []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.append(cur)
            for nxt in sorted(adjacency.get(cur, set()), reverse=True):
                if nxt not in seen:
                    stack.append(nxt)
        components.append(sorted(comp))

    now = datetime.now(timezone.utc)
    updated_count = 0
    merge_count = 0

    for comp in components:
        lineage_id = f"lin-{comp[0]}"
        size = len(comp)
        prior_ids = {
            (existing_by_id[cid].lineage_id or "").strip()
            for cid in comp
            if (existing_by_id[cid].lineage_id or "").strip()
        }
        if len(prior_ids) > 1:
            merge_count += 1

        for cid in comp:
            degree = len(adjacency.get(cid, set()))
            if size <= 1:
                confidence = 0.2
            else:
                confidence = min(1.0, 0.3 + 0.2 * min(degree, 3) + 0.1 * min(size - 1, 5))
            confidence = round(float(confidence), 3)

            row = existing_by_id[cid]
            if row.lineage_id != lineage_id or (row.lineage_confidence is None or abs(float(row.lineage_confidence) - confidence) > 1e-9):
                updated_count += 1
                row.lineage_id = lineage_id
                row.lineage_confidence = confidence
                row.lineage_updated_at = now

    db.flush()
    return LineageAssignmentResult(
        catalog_count=len(catalogs),
        component_count=len(components),
        merge_count=merge_count,
        updated_count=updated_count,
    )
