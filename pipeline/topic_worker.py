import os
import json
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

def run_topic_modeling():
    """
    Analyzes the text of all documents to discover recurring themes (topics).
    Assigns the most relevant topic keywords to each document.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Fetch documents that have text content
    documents = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != ""
    ).all()

    if not documents:
        print("No documents found for topic modeling.")
        return

    print(f"Preparing to model topics for {len(documents)} documents...")

    # PERFORMANCE: Limit text length and exclude "noise" words common in meeting minutes
    # These words appear in every meeting and don't help distinguish topics.
    custom_stop_words = [
        'council', 'meeting', 'minutes', 'motion', 'second', 'ayes', 'noes', 
        'absent', 'resolution', 'ordinance', 'city', 'approved', 'item', 'staff'
    ]
    
    # Limit each doc to first 50k chars to prevent memory issues
    texts = [doc.content[:50000] for doc in documents]

    try:
        # 1. Vectorize: Convert text into word counts
        # max_df=0.95 means ignore words that appear in more than 95% of docs
        # min_df=2 means ignore words that appear in only 1 doc
        vectorizer = CountVectorizer(
            stop_words='english', 
            max_df=0.95, 
            min_df=2
        )
        data_vectorized = vectorizer.fit_transform(texts)

        # 2. LDA: The "Topic Discovery" engine. We look for 10 distinct topics.
        lda_model = LatentDirichletAllocation(
            n_components=10, 
            random_state=42, 
            learning_method='online'
        )
        lda_output = lda_model.fit_transform(data_vectorized)

        # 3. Extract Keywords: Map the top words back to each topic
        feature_names = vectorizer.get_feature_names_out()
        topic_keywords = []
        for topic_idx, topic in enumerate(lda_model.components_):
            # Get the top 5 words for this topic
            top_words = [feature_names[i] for i in topic.argsort()[:-6:-1]]
            # Filter out our custom administrative stop words
            clean_words = [w for w in top_words if w.lower() not in custom_stop_words]
            topic_keywords.append(clean_words[:3]) # Keep top 3

        # 4. Assign to Documents: Match each doc to its most probable topic
        for i, record in enumerate(documents):
            # lda_output[i] is a list of probabilities for each topic
            dominant_topic_idx = lda_output[i].argmax()
            record.topics = topic_keywords[dominant_topic_idx]
            
        session.commit()
        print("Topic modeling complete. Keywords assigned to all documents.")

    except Exception as e:
        print(f"Error during topic modeling: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_topic_modeling()
