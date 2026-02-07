import pytest
import numpy as np
from pipeline.similarity_worker import run_similarity_engine
from pipeline.models import Catalog

def test_similarity_clustering(db_session, mocker):
    """
    Test: Does the system correctly link documents with similar semantic 'meaning'?
    """
    # 1. Setup Mock Documents
    doc1 = Catalog(id=1, filename="bike1.pdf", url_hash="bike1", content="Bike lanes and cycling.")
    doc2 = Catalog(id=2, filename="bike2.pdf", url_hash="bike2", content="Cycle tracks and paths.")
    doc3 = Catalog(id=3, filename="zone1.pdf", url_hash="zone1", content="Zoning for high density.")
    doc4 = Catalog(id=4, filename="zone2.pdf", url_hash="zone2", content="Housing development density.")

    db_session.add_all([doc1, doc2, doc3, doc4])
    db_session.commit()

    # 2. Mocking
    mock_model = mocker.Mock()
    mock_model.encode.return_value = np.zeros((4, 384))
    mocker.patch('pipeline.similarity_worker.SentenceTransformer', return_value=mock_model)
    
    mock_faiss = mocker.Mock()
    mocker.patch('pipeline.similarity_worker.faiss', mock_faiss)
    
    # Configure faiss search results
    # bike1 (index 0) finds bike2 (index 1)
    # zone1 (index 2) finds zone2 (index 3)
    mock_indices = np.array([
        [0, 1, -1, -1],
        [1, 0, -1, -1],
        [2, 3, -1, -1],
        [3, 2, -1, -1],
    ])
    mock_distances = np.array([
        [1.0, 0.9, 0.0, 0.0],
        [1.0, 0.9, 0.0, 0.0],
        [1.0, 0.9, 0.0, 0.0],
        [1.0, 0.9, 0.0, 0.0],
    ])
    mock_faiss.IndexFlatIP.return_value.search.return_value = (mock_distances, mock_indices)

    # 3. Action
    run_similarity_engine()

    # 4. Verify
    db_session.refresh(doc1)
    db_session.refresh(doc3)
    
    assert 2 in doc1.related_ids
    assert 4 in doc3.related_ids

def test_similarity_threshold(db_session, mocker):
    """
    Test: Does the system correctly ignore documents that aren't similar enough?
    """
    doc1 = Catalog(id=1, filename="cats.pdf", url_hash="cats", content="Council discussed pet licenses.")
    doc2 = Catalog(id=2, filename="roads.pdf", url_hash="roads", content="Potholes on main street.")

    db_session.add_all([doc1, doc2])
    db_session.commit()

    # Mocking
    mock_model = mocker.Mock()
    mock_model.encode.return_value = np.zeros((2, 384))
    mocker.patch('pipeline.similarity_worker.SentenceTransformer', return_value=mock_model)
    
    mock_faiss = mocker.Mock()
    mocker.patch('pipeline.similarity_worker.faiss', mock_faiss)
    
    # Configure faiss search results with LOW similarity (0.1)
    mock_indices = np.array([
        [0, 1],
        [1, 0],
    ])
    mock_distances = np.array([
        [1.0, 0.1],
        [1.0, 0.1],
    ])
    mock_faiss.IndexFlatIP.return_value.search.return_value = (mock_distances, mock_indices)

    run_similarity_engine()

    db_session.refresh(doc1)
    # related_ids should be empty because 0.1 < 0.35 threshold
    assert not doc1.related_ids or 2 not in doc1.related_ids
