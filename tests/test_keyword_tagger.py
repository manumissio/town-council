import pytest
from pipeline.topic_worker import run_keyword_tagger
from pipeline.models import Catalog

def test_keyword_uniqueness(db_session, mocker):
    """
    Verify that TF-IDF correctly identifies unique words as topics.
    """
    # 1. Setup Data
    # Documents 1 & 2 are about 'Parking'
    # Document 3 is uniquely about 'Cannabis'
    doc1 = Catalog(filename="p1.pdf", url_hash="hash1", content="Parking is a major issue in the downtown area. Parking meters are full.")
    doc2 = Catalog(filename="p2.pdf", url_hash="hash2", content="We need more parking spaces. Parking is expensive.")
    doc3 = Catalog(filename="unique.pdf", url_hash="hash3", content="The council discussed cannabis licensing and cannabis dispensaries.")

    db_session.add_all([doc1, doc2, doc3])
    db_session.commit()

    # 2. Action: Run the tagger
    run_keyword_tagger()

    # 3. Verify
    db_session.refresh(doc3)
    assert doc3.topics is not None
    # 'Cannabis' should be a top keyword for Doc 3 because it's unique to it
    assert "cannabis" in [t.lower() for t in doc3.topics]

def test_stopword_filtering(db_session, mocker):
    """
    Verify that procedural noise like 'Meeting' is filtered out.
    """
    doc = Catalog(filename="noise.pdf", url_hash="noise1", content="Meeting city council minutes meeting city council.")
    doc2 = Catalog(filename="noise2.pdf", url_hash="noise2", content="Meeting city council minutes.")
    db_session.add_all([doc, doc2])
    db_session.commit()

    run_keyword_tagger()

    db_session.refresh(doc)
    # Common words like 'meeting' should NOT be in topics
    assert "meeting" not in [t.lower() for t in doc.topics]