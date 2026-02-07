import pytest
import numpy as np
import datetime
import sys
from unittest.mock import MagicMock

# We mock the heavy libraries BEFORE importing the worker
# This prevents ModuleNotFoundError in environments without AI libraries
mock_st = MagicMock()
mock_faiss = MagicMock()
sys.modules["sentence_transformers"] = mock_st
sys.modules["faiss"] = mock_faiss

from pipeline.models import Catalog, Base
from pipeline.similarity_worker import run_similarity_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Temporary in-memory database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_similarity_clustering(db_session, mocker):
    """
    Test: Does the system correctly link documents with similar semantic 'meaning'?
    """
    # 1. Setup Mock Documents
    doc1 = Catalog(id=1, filename="bike1.pdf", content="Bike lanes and cycling.")
    doc2 = Catalog(id=2, filename="bike2.pdf", content="Cycle tracks and paths.")
    doc3 = Catalog(id=3, filename="zone1.pdf", content="Zoning for high density.")
    doc4 = Catalog(id=4, filename="zone2.pdf", content="Housing development density.")
    
    db_session.add_all([doc1, doc2, doc3, doc4])
    db_session.commit()

    # 2. Configure Mocks
    # Mock SentenceTransformer.encode to return distinguishable vectors
    def mock_encode(sentences, **kwargs):
        vecs = []
        for s in sentences:
            v = np.zeros(384, dtype='float32')
            if "bike" in s.lower() or "cycle" in s.lower():
                v[0] = 1.0 
            elif "zoning" in s.lower() or "housing" in s.lower():
                v[1] = 1.0
            vecs.append(v)
        return np.array(vecs)

    mock_model = MagicMock()
    mock_model.encode = mock_encode
    mock_st.SentenceTransformer.return_value = mock_model

    # Mock FAISS search to return the correct neighbors
    # In FAISS: index.search returns (distances, indices)
    def mock_search(embeddings, k):
        # embeddings is [4, 384]
        # indices should be [4, k]
        indices = []
        distances = []
        for i, v in enumerate(embeddings):
            if v[0] == 1.0: # Bike cluster
                # Top matches: self (0.0 dist), other bike (0.0 dist), then junk
                indices.append([i, (1 if i==0 else 0), -1, -1])
                distances.append([1.0, 1.0, 0.0, 0.0])
            else: # Housing cluster
                indices.append([i, (3 if i==2 else 2), -1, -1])
                distances.append([1.0, 1.0, 0.0, 0.0])
        return np.array(distances), np.array(indices)

    mock_index = MagicMock()
    mock_index.search = mock_search
    mock_faiss.IndexFlatIP.return_value = mock_index

    mocker.patch('pipeline.similarity_worker.db_connect', return_value=db_session.get_bind())

    # 3. Action
    run_similarity_engine()

    # 4. Verify
    r1 = db_session.get(Catalog, 1)
    assert 2 in r1.related_ids
    assert 3 not in r1.related_ids
    
    r3 = db_session.get(Catalog, 3)
    assert 4 in r3.related_ids
    assert 1 not in r3.related_ids

def test_similarity_threshold(db_session, mocker):
    """
    Test: Does the system correctly ignore documents that aren't similar enough?
    """
    doc1 = Catalog(id=1, filename="cats.pdf", content="Council discussed pet licenses.")
    doc2 = Catalog(id=2, filename="roads.pdf", content="Potholes on main street.")
    
    db_session.add_all([doc1, doc2])
    db_session.commit()

    # Mock distant vectors
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([
        np.array([1.0] + [0.0]*383, dtype='float32'),
        np.array([0.0] + [1.0]*383, dtype='float32')
    ])
    mock_st.SentenceTransformer.return_value = mock_model

    # Mock FAISS to return a low similarity score (0.1)
    mock_index = MagicMock()
    mock_index.search.return_value = (
        np.array([[1.0, 0.1], [1.0, 0.1]]), # Distances
        np.array([[0, 1], [1, 0]])          # Indices
    )
    mock_faiss.IndexFlatIP.return_value = mock_index

    mocker.patch('pipeline.similarity_worker.db_connect', return_value=db_session.get_bind())

    run_similarity_engine()

    r1 = db_session.get(Catalog, 1)
    # 0.1 is below 0.35 threshold
    assert len(r1.related_ids) == 0
