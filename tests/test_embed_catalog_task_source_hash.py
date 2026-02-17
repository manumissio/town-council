import numpy as np
from sqlalchemy.orm import sessionmaker

from pipeline.models import Catalog, SemanticEmbedding
from pipeline import tasks


def test_embed_catalog_task_skips_when_source_hash_unchanged(db_session, monkeypatch):
    catalog = Catalog(id=77, url_hash="u77", summary="Budget allocation update")
    db_session.add(catalog)
    db_session.commit()

    Session = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(tasks, "SessionLocal", Session)
    monkeypatch.setattr(tasks, "SEMANTIC_ENABLED", True)
    monkeypatch.setattr(tasks, "SEMANTIC_BACKEND", "pgvector")
    monkeypatch.setattr(tasks, "SEMANTIC_MODEL_NAME", "all-MiniLM-L6-v2")
    monkeypatch.setattr(tasks, "SEMANTIC_CONTENT_MAX_CHARS", 4000)

    from pipeline.semantic_index import PgvectorSemanticBackend

    monkeypatch.setattr(
        PgvectorSemanticBackend,
        "_encode",
        lambda self, texts: np.ones((1, 384), dtype=np.float32),
    )

    first = tasks.embed_catalog_task.run(77)
    assert first["status"] == "updated"
    assert first["embedding_dim"] == 384

    second = tasks.embed_catalog_task.run(77)
    assert second["status"] == "cached"

    rows = db_session.query(SemanticEmbedding).filter(SemanticEmbedding.catalog_id == 77).all()
    assert len(rows) == 1
    assert rows[0].source_hash is not None
