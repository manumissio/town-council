from pipeline.lineage_service import compute_lineage_assignments
from pipeline.models import Catalog


def test_lineage_component_assignment_deterministic_ids(db_session):
    c1 = Catalog(id=1, url_hash="u1", related_ids=[2])
    c2 = Catalog(id=2, url_hash="u2", related_ids=[1, 3])
    c3 = Catalog(id=3, url_hash="u3", related_ids=[2])
    c9 = Catalog(id=9, url_hash="u9", related_ids=[])
    db_session.add_all([c1, c2, c3, c9])
    db_session.commit()

    result = compute_lineage_assignments(db_session, min_edge_confidence=0.5, require_mutual_edges=False)
    db_session.commit()

    rows = {c.id: c for c in db_session.query(Catalog).all()}
    assert result.catalog_count == 4
    assert result.component_count == 2
    assert rows[1].lineage_id == "lin-1"
    assert rows[2].lineage_id == "lin-1"
    assert rows[3].lineage_id == "lin-1"
    assert rows[9].lineage_id == "lin-9"
