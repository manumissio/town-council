import logging
import re
from sqlalchemy import or_

from pipeline.models import Catalog, Document
from pipeline.db_session import db_session
from pipeline.config import (
    PROGRESS_LOG_INTERVAL
)
from pipeline.profiling import apply_catalog_id_scope
from pipeline.text_cleaning import postprocess_extracted_text

LOGGER_NAME = "topic-worker"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the entrypoint so imports stay side-effect free."""
    logging.basicConfig(level=logging.INFO, format=LOGGER_FORMAT)

# MUNICIPAL STOP WORDS
# These are words that appear constantly in city documents but aren't useful as 'Topics'.
# We filter these out so they don't drown out real topics like 'Housing' or 'Biking'.
CITY_STOP_WORDS = [
    "meeting", "council", "city", "minutes", "agenda", "present", "absent", "motion", 
    "seconded", "voted", "item", "resolution", "ordinance", "approved", 
    "unanimous", "quorum", "adjourned", "p.m.", "a.m.", "january", "february",
    "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday", 
    "friday", "hereby", "thereof", "therein", "clerk", "mayor", "councilmember",
    "commission", "committee", "commissioner", "members", "teleconference",
    "staff", "report", "public", "comment", "called", "order",
    "action", "discussion", "held", "held", "carried", "aye", "noes", "abstain",
    # Agenda templates often include "Subject:" / "Recommended Action:" labels.
    "subject", "recommended", "recommendation",
    # URL fragments are not meaningful topics, but can easily win TF-IDF on agenda PDFs.
    "http", "https", "www"
]

def _sanitize_text_for_topics(text: str) -> str:
    """
    Remove obvious noise tokens before TF-IDF.

    Why this matters:
    Without sanitation, a document with many links can produce "topics" like
    "HTTP Cupertino", which is useless to end users and looks buggy.
    """
    if not text:
        return ""

    # Clean extraction artifacts first (spaced ALLCAPS, etc.).
    value = postprocess_extracted_text(text)
    value = re.sub(r"https?://\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"www\.\S+", " ", value, flags=re.IGNORECASE)
    # Leave a trailing space so we don't create accidental word joins.
    value = re.sub(r"\bhttps?\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bwww\b", " ", value, flags=re.IGNORECASE)
    # Page markers are useful for deep linking, but not for topic discovery.
    value = re.sub(r"\[PAGE\s+\d+\]", " ", value, flags=re.IGNORECASE)
    return value

def run_keyword_tagger():
    """
    Alias for run_topic_tagger to match test expectations.
    """
    run_topic_tagger()


def select_catalog_ids_for_topic_hydration(session, limit: int | None = None) -> list[int]:
    query = (
        session.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Catalog.content.isnot(None), Catalog.content != "")
        .filter(
            or_(
                Catalog.topics.is_(None),
                Catalog.content_hash.is_(None),
                Catalog.topics_source_hash.is_(None),
                Catalog.topics_source_hash != Catalog.content_hash,
            )
        )
        .order_by(Catalog.id)
        .distinct()
    )
    query = apply_catalog_id_scope(query, Catalog.id)
    if limit is not None:
        query = query.limit(limit)
    return [int(row[0]) for row in query.all()]


def run_topic_hydration_backfill(
    *,
    force: bool = True,
    limit: int | None = None,
    max_corpus_docs: int = 600,
    catalog_ids: list[int] | None = None,
) -> dict[str, int]:
    if catalog_ids is None:
        with db_session() as session:
            catalog_ids = select_catalog_ids_for_topic_hydration(session, limit=limit)

    catalog_ids = [int(cid) for cid in catalog_ids]
    counts = {
        "selected": len(catalog_ids),
        "complete": 0,
        "cached": 0,
        "stale": 0,
        "blocked_low_signal": 0,
        "error": 0,
        "other": 0,
    }
    if not catalog_ids:
        logger.info("topic_hydration_backfill selected=0")
        return counts

    from pipeline.enrichment_tasks import generate_topics_task

    for index, catalog_id in enumerate(catalog_ids, start=1):
        try:
            result = generate_topics_task.run(
                catalog_id,
                force=force,
                max_corpus_docs=max_corpus_docs,
            )
        except Exception as exc:
            counts["error"] += 1
            logger.warning(
                "topic_hydration catalog_id=%s status=error error=%s",
                catalog_id,
                exc,
                exc_info=True,
            )
            continue

        status = str((result or {}).get("status") or "").strip() or ("error" if (result or {}).get("error") else "other")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
        if index == 1 or index % PROGRESS_LOG_INTERVAL == 0 or index == len(catalog_ids):
            logger.info(
                "topic_hydration_backfill progress=%s/%s last_catalog_id=%s last_status=%s",
                index,
                len(catalog_ids),
                catalog_id,
                status,
            )

    logger.info(
        "topic_hydration_backfill selected=%s complete=%s cached=%s stale=%s blocked_low_signal=%s error=%s other=%s",
        counts["selected"],
        counts["complete"],
        counts["cached"],
        counts["stale"],
        counts["blocked_low_signal"],
        counts["error"],
        counts["other"],
    )
    return counts

def run_topic_tagger():
    """
    Automated Topic Discovery using TF-IDF.

    What this does:
    1. Fetches all documents from the database
    2. Analyzes text to find the most distinctive words/phrases in each document
    3. Tags each document with its top 5 keywords (topics)

    What is TF-IDF?
    Term Frequency-Inverse Document Frequency. It finds words that are:
    - Common in THIS document (Term Frequency)
    - Rare across ALL documents (Inverse Document Frequency)

    For example, if "housing" appears 50 times in one meeting but only 3 times
    in others, it's likely an important topic for that specific meeting.
    """
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

    from pipeline.content_hash import compute_content_hash
    from pipeline.indexer import reindex_catalogs
    from pipeline.config import (
        MAX_CONTENT_LENGTH,
        TFIDF_MAX_DF,
        TFIDF_MIN_DF,
        TFIDF_NGRAM_RANGE,
        TFIDF_MAX_FEATURES,
        TOP_KEYWORDS_PER_DOC,
    )

    # Use context manager for automatic session cleanup and error handling
    with db_session() as session:
        # 1. Fetch all documents that have text content
        logger.info("Fetching documents for topic analysis...")
        records = session.query(Catalog).filter(
            Catalog.content != None,
            Catalog.content != ""
        )
        records = apply_catalog_id_scope(records, Catalog.id).all()

        # Pre-initialize topics to empty lists
        # Why? Some documents might have no valid topics, we want [] not None
        touched_catalog_ids: set[int] = set()
        for r in records:
            # Track which extracted text version topics were generated from.
            # If content changes later (re-extraction), topics become "stale" by hash mismatch.
            if r.content and not getattr(r, "content_hash", None):
                r.content_hash = compute_content_hash(r.content)
            r.topics = []
            touched_catalog_ids.add(r.id)

        if len(records) < 2:
            logger.warning("Not enough documents to perform TF-IDF analysis.")
            session.commit()
            return

        # 2. Prepare the corpus (the collection of all documents)
        # We truncate each document to prevent memory issues with very large PDFs
        corpus = [_sanitize_text_for_topics(r.content[:MAX_CONTENT_LENGTH]) for r in records]
        filenames = [r.filename for r in records]

        logger.info(f"Analyzing {len(corpus)} documents...")

        # 3. Setup the TF-IDF Vectorizer
        # This is the "brain" that calculates which words are important
        stop_words = sorted(set(CITY_STOP_WORDS).union(ENGLISH_STOP_WORDS))
        vectorizer = TfidfVectorizer(
            stop_words=stop_words,  # Filter out common municipal + English words
            max_df=TFIDF_MAX_DF,  # Ignore words in >80% of docs (too common)
            min_df=TFIDF_MIN_DF,  # Allow words in just 1 doc (unique topics)
            max_features=TFIDF_MAX_FEATURES,  # Track top 5000 words globally
            ngram_range=TFIDF_NGRAM_RANGE,  # Catch phrases like "Rent Control"
            # Drop pure numbers and very short tokens so dates/years don't become "topics".
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z']{2,}\b",
        )

        # 4. Run the TF-IDF analysis across all documents
        # This creates a mathematical matrix where each document is a vector of word scores
        try:
            tfidf_matrix = vectorizer.fit_transform(corpus)
            feature_names = vectorizer.get_feature_names_out()
        except (ValueError, MemoryError) as e:
            # TF-IDF computation errors: What can go wrong with the math?
            # - ValueError: All documents are empty or contain only stop words
            #   (no valid features to extract)
            # - MemoryError: Too many documents or features to fit in RAM
            #   (rare, but possible with 10,000+ documents)
            # Why commit before returning? Save the empty topic lists we initialized
            # This prevents infinite retries on documents that legitimately have no topics
            logger.error(f"TF-IDF math failed: {e}")
            session.commit()
            summary = reindex_catalogs(touched_catalog_ids)
            logger.info(
                "topic_reindex_summary considered=%s reindexed=%s failed=%s",
                summary["catalogs_considered"],
                summary["catalogs_reindexed"],
                summary["catalogs_failed"],
            )
            return

        # 5. Extract the top keywords for each document
        for i, record in enumerate(records):
            # Initialize to empty list
            record.topics = []
            record.topics_source_hash = record.content_hash

            try:
                # Get the scores for this specific document
                # This is a row in the matrix with a score for each word
                doc_vector = tfidf_matrix[i].toarray()[0]

                # Sort words by their score (highest = most important)
                # [-N:] gets the last N items (highest), [::-1] reverses to descending order
                top_indices = doc_vector.argsort()[-TOP_KEYWORDS_PER_DOC:][::-1]

                # Only keep words with a score > 0 (meaning they actually appeared)
                keywords = [feature_names[idx] for idx in top_indices if doc_vector[idx] > 0]

                # Clean up: Capitalize for better display in the UI
                # "housing crisis" becomes "Housing Crisis"
                record.topics = [k.title() for k in keywords]
                record.topics_source_hash = record.content_hash
            except (IndexError, ValueError):
                # Individual document errors: What can fail for a single document?
                # - IndexError: Document has no valid tokens after filtering
                #   (document was all stop words like "the meeting was called to order")
                # - ValueError: Document vector is malformed (extremely rare)
                # Why continue instead of failing? One bad document shouldn't stop
                # topic extraction for thousands of other documents. This document
                # will just have an empty topics list.
                record.topics_source_hash = record.content_hash
                continue

            # Log progress every N documents to track processing
            if i % PROGRESS_LOG_INTERVAL == 0:
                logger.info(f"Processed {i}/{len(records)} documents...")

        # 6. Save all new topics to the database
        # The context manager will automatically rollback if this fails
        session.commit()
        summary = reindex_catalogs(touched_catalog_ids)
        logger.info(
            "topic_reindex_summary considered=%s reindexed=%s failed=%s",
            summary["catalogs_considered"],
            summary["catalogs_reindexed"],
            summary["catalogs_failed"],
        )
        logger.info("Topic tagging complete and saved to database.")


def main() -> int:
    _configure_cli_logging()
    run_topic_tagger()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
