from pipeline.content_hash import compute_content_hash
from pipeline.nlp_worker import build_entity_candidate_text
from pipeline.models import Catalog, Document, Event, Place
from pipeline.run_pipeline import select_catalog_ids_for_entity_backfill


def test_build_entity_candidate_text_prefers_agenda_cue_lines():
    text = "\n".join(
        [
            "Introductory boilerplate line",
            "Roll Call: Mayor Jane Smith, Councilmember Alex Brown",
            "Ayes: Jane Smith, Alex Brown",
            "Long appendix line that should not be needed for entity extraction",
        ]
    )

    candidate_text, meta = build_entity_candidate_text(text, category="agenda")

    assert "Roll Call" in candidate_text
    assert "Ayes:" in candidate_text
    assert "Introductory boilerplate line" not in candidate_text
    assert meta["skip_low_signal"] is False
    assert meta["used_prefix_fallback"] is False


def test_build_entity_candidate_text_uses_prefix_fallback_when_cues_missing():
    text = "Jane Smith spoke with Alex Brown about the zoning update before the meeting."

    candidate_text, meta = build_entity_candidate_text(text, category="agenda")

    assert candidate_text.startswith("Jane Smith")
    assert meta["used_prefix_fallback"] is True
    assert meta["skip_low_signal"] is False


def test_select_catalog_ids_for_entity_backfill_skips_fresh_rows(db_session):
    place = Place(
        name="sample",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:sample",
        crawler_name="sample",
    )
    db_session.add(place)
    db_session.flush()
    event = Event(place_id=place.id, ocd_division_id=place.ocd_division_id, name="Sample Council")
    db_session.add(event)
    db_session.flush()

    content = "Mayor Jane Smith called the meeting to order."
    content_hash = compute_content_hash(content)

    fresh_catalog = Catalog(
        url="fresh",
        url_hash="fresh",
        location="/tmp/fresh.pdf",
        filename="fresh.pdf",
        content=content,
        content_hash=content_hash,
        entities={"persons": ["Jane Smith"], "orgs": [], "locs": []},
        entities_source_hash=content_hash,
    )
    stale_catalog = Catalog(
        url="stale",
        url_hash="stale",
        location="/tmp/stale.pdf",
        filename="stale.pdf",
        content=content,
        content_hash=content_hash,
        entities={"persons": ["Jane Smith"], "orgs": [], "locs": []},
        entities_source_hash="oldhash",
    )
    db_session.add_all([fresh_catalog, stale_catalog])
    db_session.flush()

    for catalog in (fresh_catalog, stale_catalog):
        db_session.add(
            Document(
                place_id=place.id,
                event_id=event.id,
                catalog_id=catalog.id,
                category="agenda",
                url=f"https://example.com/{catalog.id}",
            )
        )
    db_session.commit()

    selected = select_catalog_ids_for_entity_backfill(db_session)

    assert fresh_catalog.id not in selected
    assert stale_catalog.id in selected
