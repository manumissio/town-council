from pipeline.lineage_service import compute_lineage_assignments
from pipeline.models import Catalog


def test_lineage_component_merge_rewrite(db_session):
    a = Catalog(id=10, url_hash="u10", related_ids=[11])
    b = Catalog(id=11, url_hash="u11", related_ids=[10])
    c = Catalog(id=20, url_hash="u20", related_ids=[21])
    d = Catalog(id=21, url_hash="u21", related_ids=[20])
    db_session.add_all([a, b, c, d])
    db_session.commit()

    first = compute_lineage_assignments(db_session, min_edge_confidence=0.5, require_mutual_edges=False)
    db_session.commit()
    assert first.component_count == 2

    # Bridge node merges both prior components.
    bridge = Catalog(id=15, url_hash="u15", related_ids=[11, 20])
    db_session.add(bridge)
    db_session.commit()

    second = compute_lineage_assignments(db_session, min_edge_confidence=0.5, require_mutual_edges=False)
    db_session.commit()

    ids = {c.id: c.lineage_id for c in db_session.query(Catalog).all()}
    assert second.component_count == 1
    assert second.merge_count >= 1
    assert ids[10] == "lin-10"
    assert ids[11] == "lin-10"
    assert ids[15] == "lin-10"
    assert ids[20] == "lin-10"
    assert ids[21] == "lin-10"
