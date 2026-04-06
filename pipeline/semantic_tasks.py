import logging

from sqlalchemy.orm import sessionmaker

from pipeline.celery_app import app
from pipeline.config import (
    SEMANTIC_BACKEND,
    SEMANTIC_ENABLED,
    SEMANTIC_MODEL_NAME,
)
from pipeline.models import Catalog, SemanticEmbedding, db_connect


logger = logging.getLogger("semantic-worker")

_SessionLocal = None


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=db_connect())
    return _SessionLocal()


@app.task(bind=True, max_retries=2, name="semantic.embed_catalog")
def embed_catalog_task(self, catalog_id: int, force: bool = False):
    """
    B2 embedding task: store catalog-summary vectors in semantic_embedding for pgvector rerank.
    """
    if not SEMANTIC_ENABLED:
        return {"status": "skipped", "reason": "semantic_disabled"}
    if (SEMANTIC_BACKEND or "").strip().lower() != "pgvector":
        return {"status": "skipped", "reason": f"backend_{SEMANTIC_BACKEND}"}

    db = SessionLocal()
    try:
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            return {"status": "skipped", "reason": "catalog_missing"}

        from pipeline.semantic_index import (
            PgvectorSemanticBackend,
            catalog_semantic_source_hash,
            catalog_semantic_text,
        )

        text_payload = catalog_semantic_text(catalog.summary)
        source_hash = catalog_semantic_source_hash(catalog.summary)
        if source_hash is None:
            return {"status": "skipped", "reason": "summary_too_short"}

        existing = (
            db.query(SemanticEmbedding)
            .filter(
                SemanticEmbedding.catalog_id == catalog_id,
                SemanticEmbedding.model_name == SEMANTIC_MODEL_NAME,
            )
            .first()
        )
        if existing and existing.source_hash == source_hash and not force:
            return {"status": "cached", "catalog_id": catalog_id}

        backend = PgvectorSemanticBackend()
        vector = backend._encode([text_payload])[0].tolist()  # noqa: SLF001

        if existing is None:
            existing = SemanticEmbedding(
                catalog_id=catalog_id,
                model_name=SEMANTIC_MODEL_NAME,
                embedding_dim=len(vector),
            )
            db.add(existing)
        existing.embedding = vector
        existing.embedding_dim = len(vector)
        existing.source_hash = source_hash
        db.commit()
        return {"status": "updated", "catalog_id": catalog_id, "embedding_dim": len(vector)}
    except Exception as e:
        db.rollback()
        logger.error("embed_catalog_task failed catalog_id=%s error=%s", catalog_id, e)
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()
