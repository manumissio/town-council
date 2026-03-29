from pipeline.celery_app import app


def test_semantic_embed_task_routes_to_semantic_queue():
    assert app.conf.task_default_queue == "celery"
    assert app.conf.task_routes["semantic.embed_catalog"]["queue"] == "semantic"


def test_semantic_embed_task_has_stable_name():
    from pipeline.semantic_tasks import embed_catalog_task

    assert embed_catalog_task.name == "semantic.embed_catalog"
