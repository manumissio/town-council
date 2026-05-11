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


def test_lineage_ignores_invalid_and_missing_related_ids(db_session):
    c1 = Catalog(id=1, url_hash="u1", related_ids=[2, "bad", None, 999])
    c2 = Catalog(id=2, url_hash="u2", related_ids=[])
    db_session.add_all([c1, c2])
    db_session.commit()

    result = compute_lineage_assignments(db_session, min_edge_confidence=0.5, require_mutual_edges=False)
    db_session.commit()

    rows = {c.id: c for c in db_session.query(Catalog).all()}
    assert result.component_count == 1
    assert rows[1].lineage_id == "lin-1"
    assert rows[2].lineage_id == "lin-1"


def test_lineage_require_mutual_edges_excludes_one_way_edges(db_session):
    c1 = Catalog(id=1, url_hash="u1", related_ids=[2])
    c2 = Catalog(id=2, url_hash="u2", related_ids=[])
    db_session.add_all([c1, c2])
    db_session.commit()

    result = compute_lineage_assignments(db_session, min_edge_confidence=0.5, require_mutual_edges=True)
    db_session.commit()

    rows = {c.id: c for c in db_session.query(Catalog).all()}
    assert result.component_count == 2
    assert rows[1].lineage_id == "lin-1"
    assert rows[2].lineage_id == "lin-2"
    assert rows[1].lineage_confidence == 0.2
    assert rows[2].lineage_confidence == 0.2


def test_lineage_min_edge_confidence_keeps_only_mutual_edges_at_one(db_session):
    c1 = Catalog(id=1, url_hash="u1", related_ids=[2])
    c2 = Catalog(id=2, url_hash="u2", related_ids=[1])
    c3 = Catalog(id=3, url_hash="u3", related_ids=[4])
    c4 = Catalog(id=4, url_hash="u4", related_ids=[])
    db_session.add_all([c1, c2, c3, c4])
    db_session.commit()

    result = compute_lineage_assignments(db_session, min_edge_confidence=1.0, require_mutual_edges=False)
    db_session.commit()

    rows = {c.id: c for c in db_session.query(Catalog).all()}
    assert result.component_count == 3
    assert rows[1].lineage_id == "lin-1"
    assert rows[2].lineage_id == "lin-1"
    assert rows[3].lineage_id == "lin-3"
    assert rows[4].lineage_id == "lin-4"


def test_lineage_confidence_and_unchanged_update_count_are_stable(db_session):
    c1 = Catalog(id=1, url_hash="u1", related_ids=[2])
    c2 = Catalog(id=2, url_hash="u2", related_ids=[1, 3])
    c3 = Catalog(id=3, url_hash="u3", related_ids=[2])
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    first = compute_lineage_assignments(db_session, min_edge_confidence=0.5, require_mutual_edges=False)
    db_session.commit()
    rows = {c.id: c for c in db_session.query(Catalog).all()}
    first_updated_at = {catalog_id: row.lineage_updated_at for catalog_id, row in rows.items()}

    second = compute_lineage_assignments(db_session, min_edge_confidence=0.5, require_mutual_edges=False)
    db_session.commit()
    refreshed = {c.id: c for c in db_session.query(Catalog).all()}

    assert first.updated_count == 3
    assert second.updated_count == 0
    assert refreshed[1].lineage_confidence == 0.7
    assert refreshed[2].lineage_confidence == 0.9
    assert refreshed[3].lineage_confidence == 0.7
    assert {catalog_id: row.lineage_updated_at for catalog_id, row in refreshed.items()} == first_updated_at
