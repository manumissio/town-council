import pytest
from pipeline.models import Catalog, Base
from pipeline.similarity_worker import run_similarity_engine
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

def test_similarity_clustering(db_session, mocker):
    """
    Verify that similar documents are linked together.
    """
    # 1. Setup Cluster 1: Biking
    doc1 = Catalog(id=1, filename="bike1.pdf", content="We need more bike lanes and cycling infrastructure.")
    doc2 = Catalog(id=2, filename="bike2.pdf", content="Biking is safe and we should build more cycle tracks.")
    
    # 2. Setup Cluster 2: Zoning
    doc3 = Catalog(id=3, filename="zone1.pdf", content="Zoning laws for high density housing units.")
    doc4 = Catalog(id=4, filename="zone2.pdf", content="Housing and development density zoning updates.")
    
    db_session.add_all([doc1, doc2, doc3, doc4])
    db_session.commit()

    # 3. Mock DB connection
    mocker.patch('pipeline.similarity_worker.db_connect', return_value=db_session.get_bind())

    # 4. Action
    run_similarity_engine()

    # 5. Verify
    # Bike 1 should be linked to Bike 2
    r1 = db_session.get(Catalog, 1)
    assert 2 in r1.related_ids
    assert 3 not in r1.related_ids # Should NOT be linked to Zoning
    
    # Zone 1 should be linked to Zone 2
    r3 = db_session.get(Catalog, 3)
    assert 4 in r3.related_ids
    assert 1 not in r3.related_ids # Should NOT be linked to Biking

def test_similarity_no_matches(db_session, mocker):
    """
    Verify that completely unrelated documents aren't forced together.
    """
    doc1 = Catalog(id=1, filename="cats.pdf", content="The council discussed pet licenses for cats.")
    doc2 = Catalog(id=2, filename="roads.pdf", content="Potholes on main street need to be repaired.")
    
    db_session.add_all([doc1, doc2])
    db_session.commit()

    mocker.patch('pipeline.similarity_worker.db_connect', return_value=db_session.get_bind())
    run_similarity_engine()

    r1 = db_session.get(Catalog, 1)
    # The score should be below our 0.1 threshold
    assert len(r1.related_ids) == 0
