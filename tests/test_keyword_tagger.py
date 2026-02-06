import pytest
from pipeline.models import Catalog, Base
from pipeline.topic_worker import run_topic_tagger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Temporary in-memory database."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_keyword_uniqueness(db_session, mocker):
    """
    Verify that TF-IDF correctly identifies unique words as topics.
    """
    # 1. Setup Data
    # Documents 1 & 2 are about 'Parking'
    # Document 3 is uniquely about 'Cannabis'
    doc1 = Catalog(filename="p1.pdf", content="Parking is a major issue in the downtown area. Parking meters are full.")
    doc2 = Catalog(filename="p2.pdf", content="We need more parking spaces. Parking is expensive.")
    doc3 = Catalog(filename="unique.pdf", content="The council discussed cannabis licensing and cannabis dispensaries.")
    
    db_session.add_all([doc1, doc2, doc3])
    db_session.commit()

    # 2. Mock DB connection in worker
    mocker.patch('pipeline.topic_worker.db_connect', return_value=db_session.get_bind())

    # 3. Action
    run_topic_tagger()

    # 4. Verify
    unique_record = db_session.query(Catalog).filter_by(filename="unique.pdf").first()
    assert unique_record.topics is not None
    # 'Cannabis' should be a top topic because it only appears in this document
    assert "Cannabis" in unique_record.topics
    
    # 'Parking' should NOT be a top topic for the cannabis document
    assert "Parking" not in unique_record.topics

def test_stopword_filtering(db_session, mocker):
    """
    Verify that procedural noise like 'Meeting' is filtered out.
    """
    doc = Catalog(filename="noise.pdf", content="Meeting city council minutes meeting city council.")
    doc2 = Catalog(filename="noise2.pdf", content="Meeting city council minutes.")
    db_session.add_all([doc, doc2])
    db_session.commit()

    mocker.patch('pipeline.topic_worker.db_connect', return_value=db_session.get_bind())
    run_topic_tagger()

    record = db_session.query(Catalog).filter_by(filename="noise.pdf").first()
    # Procedural words should be blocked by CITY_STOP_WORDS
    assert "Meeting" not in record.topics
    assert "Council" not in record.topics
