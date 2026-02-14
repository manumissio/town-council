from types import SimpleNamespace


def test_generate_topics_task_handles_single_doc_corpus(mocker):
    """
    Regression: per-catalog topic regeneration should not crash when a city has only
    one extracted document with content (common in dev after startup purge).
    """
    from pipeline import tasks

    catalog_id = 401
    catalog = SimpleNamespace(
        id=catalog_id,
        content="""
        [PAGE 1]
        NEW BUSINESS
        1. Subject: Cupertino Crash Data Analysis (Ganga)
        2. Subject: Overview of California E-Scooter Policy (Condamoor)
        https://example.com
        """,
        topics=None,
        content_hash=None,
        topics_source_hash=None,
    )
    doc = SimpleNamespace(catalog_id=catalog_id, place_id=2)

    class _FakeQuery:
        def __init__(self, rows=None, doc=None):
            self._rows = rows
            self._doc = doc

        def filter_by(self, **kwargs):
            return self

        def first(self):
            return self._doc

        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def all(self):
            return self._rows

    class _FakeSession:
        def get(self, model, _id):
            return catalog

        def query(self, *models):
            model = models[0] if models else None
            # Document lookup
            if getattr(model, "__name__", "") == "Document":
                return _FakeQuery(doc=doc)
            # Corpus query returns a single doc row
            return _FakeQuery(rows=[(catalog_id, catalog.content)])

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    mocker.patch.object(tasks, "SessionLocal", return_value=_FakeSession())
    # Avoid touching the search index in a unit test.
    mocker.patch.object(tasks, "reindex_catalog", side_effect=Exception("skip"))

    result = tasks.generate_topics_task.run(catalog_id, force=True)
    assert result["status"] in ("complete", "blocked_low_signal")
    if result["status"] == "complete":
        # Ensure we did not emit date tokens or URL fragments as "topics".
        lowered = " ".join(result.get("topics") or []).lower()
        assert "september" not in lowered
        assert "http" not in lowered
        # Ensure we don't just emit generic scaffolding words.
        assert "subject" not in lowered
        # And that at least one real term survives.
        assert any(k in lowered for k in ("crash", "scooter", "policy"))
