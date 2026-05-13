from pipeline.celery_app import app


def test_enrichment_topics_task_routes_to_enrichment_queue():
    assert app.conf.task_default_queue == "celery"
    assert app.conf.task_routes["enrichment.generate_topics"]["queue"] == "enrichment"


def test_enrichment_topics_task_has_stable_name():
    from pipeline.enrichment_tasks import generate_topics_task

    assert generate_topics_task.name == "enrichment.generate_topics"


def test_api_topics_dispatch_uses_registered_enrichment_task():
    from api.task_dispatch import GENERATE_TOPICS_TASK_NAME
    from pipeline.enrichment_tasks import generate_topics_task

    assert GENERATE_TOPICS_TASK_NAME == generate_topics_task.name


def test_api_topics_dispatch_routes_to_enrichment_queue():
    from api.task_dispatch import GENERATE_TOPICS_TASK_NAME

    assert app.conf.task_routes[GENERATE_TOPICS_TASK_NAME]["queue"] == "enrichment"
