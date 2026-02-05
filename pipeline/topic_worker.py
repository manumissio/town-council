import os
import json
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

def run_topic_modeling():
    """
    Scans all meeting minutes to automatically discover recurring themes (e.g., "Housing", "Traffic").
    
    How it works (Latent Dirichlet Allocation - LDA):
    1. It reads all the text from every document.
    2. It finds words that frequently appear together (forming a "topic").
    3. It tags each document with the 3 most relevant keywords for its main topic.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find all documents that have text content.
    documents = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != ""
    ).all()

    if not documents:
        print("No documents found for topic modeling.")
        return

    print(f"Preparing to model topics for {len(documents)} documents...")

    # Define a list of "noise" words to ignore.
    # These words appear in almost every meeting ("motion", "second", "council") so they
    # don't help us distinguish between different types of meetings (like Zoning vs. Budget).
    custom_stop_words = [
        'council', 'meeting', 'minutes', 'motion', 'second', 'ayes', 'noes', 
        'absent', 'resolution', 'ordinance', 'city', 'approved', 'item', 'staff'
    ]
    
    # Performance Optimization: Only use the first 50,000 characters of each document.
    # This keeps memory usage low while still capturing the main content.
    texts = [doc.content[:50000] for doc in documents]

    try:
        # Step 1: Count how many times each word appears in each document.
        # - stop_words='english': Removes common words like "the", "and", "is".
        # - max_df=0.95: Ignore words that appear in more than 95% of documents (too common).
        # - min_df=2: Ignore words that appear in only 1 document (too rare).
        vectorizer = CountVectorizer(
            stop_words='english', 
            max_df=0.95, 
            min_df=2
        )
        data_vectorized = vectorizer.fit_transform(texts)

        # Step 2: Run the Topic Modeling algorithm (LDA).
        # We ask it to find 10 distinct topics across our collection of documents.
        lda_model = LatentDirichletAllocation(
            n_components=10, 
            random_state=42, 
            learning_method='online'
        )
        lda_output = lda_model.fit_transform(data_vectorized)

        # Step 3: Figure out which words best describe each topic.
        feature_names = vectorizer.get_feature_names_out()
        topic_keywords = []
        for topic_idx, topic in enumerate(lda_model.components_):
            # Get the top 5 most important words for this topic.
            top_words = [feature_names[i] for i in topic.argsort()[:-6:-1]]
            # Remove any of our custom "noise" words if they snuck in.
            clean_words = [w for w in top_words if w.lower() not in custom_stop_words]
            # Save the top 3 keywords to describe this topic.
            topic_keywords.append(clean_words[:3])

        # Step 4: Tag each document with its main topic.
        for i, record in enumerate(documents):
            # lda_output[i] gives us the probability of each topic for document[i].
            # We pick the one with the highest probability.
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