from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Catalog, AgendaItem
from pipeline.startup_purge import purge_derived_state


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_purge_clears_catalog_derived_fields_and_agenda_items():
    s = _session()

    c = Catalog(
        url="http://example.com/a.pdf",
        url_hash="h1",
        location="/tmp/a.pdf",
        content="Some extracted text",
        content_hash="content_hash",
        summary="summary",
        summary_source_hash="content_hash",
        summary_extractive="extractive",
        topics=["Budget"],
        topics_source_hash="content_hash",
        entities={"orgs": ["City"]},
        related_ids=[1, 2],
        tables=[{"rows": 1}],
    )
    s.add(c)
    s.commit()

    s.add(AgendaItem(event_id=1, catalog_id=c.id, title="Item 1", order=1))
    s.commit()

    counts = purge_derived_state(s)
    s.commit()

    refreshed = s.get(Catalog, c.id)
    assert counts["deleted_agenda_items"] == 1
    assert counts["cleared_catalog_rows"] == 1
    assert refreshed.content is None
    assert refreshed.summary is None
    assert refreshed.summary_extractive is None
    assert refreshed.topics is None
    assert refreshed.entities is None
    assert refreshed.related_ids is None
    assert refreshed.tables is None
    assert refreshed.content_hash is None
    assert refreshed.summary_source_hash is None
    assert refreshed.topics_source_hash is None
    assert s.query(AgendaItem).count() == 0


def test_purge_is_idempotent():
    s = _session()
    c = Catalog(url="http://example.com/b.pdf", url_hash="h2", location="/tmp/b.pdf")
    s.add(c)
    s.commit()

    first = purge_derived_state(s)
    s.commit()
    second = purge_derived_state(s)
    s.commit()

    assert first["cleared_catalog_rows"] >= 1
    assert second["cleared_catalog_rows"] >= 1
    assert s.query(AgendaItem).count() == 0
