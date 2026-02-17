from pipeline.models import SemanticEmbedding


def test_semantic_embedding_has_xor_check_constraint():
    checks = [c.sqltext.text.lower() for c in SemanticEmbedding.__table__.constraints if c.__class__.__name__ == "CheckConstraint"]
    assert any("catalog_id is not null" in c and "agenda_item_id is null" in c for c in checks)
    assert any("catalog_id is null" in c and "agenda_item_id is not null" in c for c in checks)


def test_semantic_embedding_unique_indexes_exist():
    index_names = {idx.name for idx in SemanticEmbedding.__table__.indexes}
    assert "ix_semantic_embedding_catalog_model" in index_names
    assert "ix_semantic_embedding_item_model" in index_names
