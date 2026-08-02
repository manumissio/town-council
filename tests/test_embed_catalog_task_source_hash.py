import numpy as np
from sqlalchemy.orm import sessionmaker

import pipeline.semantic_backend_runtime as semantic_backend_runtime
from pipeline.models import Catalog, SemanticEmbedding
from pipeline import semantic_tasks


class _FakeSentenceTransformer:
    def __init__(self, _model_name: str):
        self.model_name = _model_name

    def encode(self, texts: list[str], *, batch_size: int, show_progress_bar: bool) -> np.ndarray:
        assert batch_size == 32
        assert show_progress_bar is False
        return np.ones((len(texts), 384), dtype=np.float32)


def test_embed_catalog_task_skips_when_source_hash_unchanged(db_session, monkeypatch):
    catalog = Catalog(id=77, url_hash="u77", summary="Budget allocation update")
    db_session.add(catalog)
    db_session.commit()

    Session = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(semantic_tasks, "SessionLocal", Session)
    monkeypatch.setattr(semantic_tasks, "SEMANTIC_ENABLED", True)
    monkeypatch.setattr(semantic_tasks, "SEMANTIC_BACKEND", "pgvector")
    monkeypatch.setattr(semantic_tasks, "SEMANTIC_MODEL_NAME", "all-MiniLM-L6-v2")
    monkeypatch.setattr(semantic_tasks, "SEMANTIC_CONTENT_MAX_CHARS", 4000)
    monkeypatch.setattr(semantic_backend_runtime, "SentenceTransformer", _FakeSentenceTransformer)

    first = semantic_tasks.embed_catalog_task.run(77)
    assert first["status"] == "updated"
    assert first["embedding_dim"] == 384

    second = semantic_tasks.embed_catalog_task.run(77)
    assert second["status"] == "cached"

    rows = db_session.query(SemanticEmbedding).filter(SemanticEmbedding.catalog_id == 77).all()
    assert len(rows) == 1
    assert rows[0].source_hash is not None
