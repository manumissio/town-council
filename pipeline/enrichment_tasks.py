import re

from sqlalchemy.exc import SQLAlchemyError

from pipeline.celery_app import app
from pipeline.content_hash import compute_content_hash
from pipeline.indexer import reindex_catalog
from pipeline.models import Catalog, Document
from pipeline.summary_quality import (
    analyze_source_text,
    build_low_signal_message,
    is_source_topicable,
)
from pipeline.tasks import SessionLocal, _extract_agenda_titles_from_text
from pipeline.text_cleaning import postprocess_extracted_text


@app.task(bind=True, max_retries=3, name="enrichment.generate_topics")
def generate_topics_task(self, catalog_id: int, force: bool = False, max_corpus_docs: int = 600):
    """
    Background task: (re)generate topic tags for a single catalog.

    Topics are derived from extracted text, so we tie them to Catalog.content_hash.
    This task uses a bounded per-city corpus to keep runtime predictable.
    """
    db = SessionLocal()
    try:
        catalog = db.get(Catalog, catalog_id)
        if not catalog or not catalog.content:
            return {"error": "No content to tag"}

        content_hash = catalog.content_hash or compute_content_hash(catalog.content)
        quality = analyze_source_text(catalog.content)
        if not is_source_topicable(quality):
            return {
                "status": "blocked_low_signal",
                "reason": build_low_signal_message(quality),
                "topics": [],
            }

        is_fresh = bool(
            catalog.topics is not None
            and content_hash
            and catalog.topics_source_hash
            and catalog.topics_source_hash == content_hash
        )
        if (not force) and is_fresh:
            return {"status": "cached", "topics": catalog.topics}
        if (not force) and catalog.topics is not None and not is_fresh:
            return {"status": "stale", "topics": catalog.topics}

        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return {"error": "Document not linked to catalog"}

        from pipeline.config import (
            MAX_CONTENT_LENGTH,
            TFIDF_MAX_DF,
            TFIDF_MIN_DF,
            TFIDF_NGRAM_RANGE,
            TFIDF_MAX_FEATURES,
        )
        from pipeline.topic_worker import CITY_STOP_WORDS, _sanitize_text_for_topics
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
        import numpy as np

        rows = (
            db.query(Catalog.id, Catalog.content)
            .join(Document, Document.catalog_id == Catalog.id)
            .filter(Document.place_id == doc.place_id, Catalog.content.isnot(None), Catalog.content != "")
            .order_by(Catalog.id.desc())
            .limit(max_corpus_docs)
            .all()
        )
        if not rows:
            return {"error": "No corpus available for topic tagging"}

        ids = [r[0] for r in rows]
        corpus = [_sanitize_text_for_topics((r[1] or "")[:MAX_CONTENT_LENGTH]) for r in rows]
        if not any(s.strip() for s in corpus):
            return {
                "status": "blocked_low_signal",
                "reason": "Not enough usable text to generate topics.",
                "topics": [],
            }

        place_tokens = set()
        try:
            from pipeline.models import Place

            place = db.get(Place, doc.place_id)
            display = (getattr(place, "display_name", "") or getattr(place, "name", "") or "").lower()
            for tok in re.findall(r"[a-zA-Z]{3,}", display):
                place_tokens.add(tok)
        except Exception:
            place_tokens = set()

        stop_words = sorted(set(CITY_STOP_WORDS).union(ENGLISH_STOP_WORDS).union(place_tokens))
        n_docs = len(corpus)

        if n_docs < 3:
            cleaned = postprocess_extracted_text(catalog.content)
            titles = _extract_agenda_titles_from_text(cleaned, max_titles=8)
            if titles:
                normalized_titles = []
                for t in titles:
                    v = re.sub(r"\([^)]*\)", " ", t)
                    v = re.sub(r"^\s*subject\s*:\s*", "", v, flags=re.IGNORECASE)
                    v = re.sub(r"^\s*recommended\s+action\s*:\s*", "", v, flags=re.IGNORECASE)
                    normalized_titles.append(v.strip())
                candidates = " ".join(normalized_titles)
            else:
                candidates = cleaned

            word_tokens = [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", candidates)]
            stop = set(stop_words)
            filtered = [t for t in word_tokens if t not in stop]
            if not filtered:
                return {
                    "status": "blocked_low_signal",
                    "reason": "Not enough usable text to generate topics.",
                    "topics": [],
                }

            phrase_counts = {}
            for n in (3, 2):
                for i in range(0, max(0, len(filtered) - n + 1)):
                    phrase = " ".join(filtered[i : i + n])
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

            unigram_counts = {}
            for token in filtered:
                unigram_counts[token] = unigram_counts.get(token, 0) + 1

            ranked_phrases = sorted(phrase_counts.items(), key=lambda kv: (-kv[1], kv[0]))
            ranked_unigrams = sorted(unigram_counts.items(), key=lambda kv: (-kv[1], kv[0]))

            keywords = []
            seen = set()
            for phrase, _count in ranked_phrases:
                key = phrase.lower()
                if key in seen:
                    continue
                seen.add(key)
                keywords.append(phrase.title())
                if len(keywords) >= 5:
                    break
            if len(keywords) < 5:
                for word, _count in ranked_unigrams:
                    key = word.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    keywords.append(word.title())
                    if len(keywords) >= 5:
                        break

            catalog.topics = keywords
            catalog.content_hash = content_hash
            catalog.topics_source_hash = content_hash
            db.commit()
            try:
                reindex_catalog(catalog_id)
            except Exception:
                pass
            return {"status": "complete", "topics": keywords}

        max_df = (1.0 if n_docs < 2 else TFIDF_MAX_DF)
        min_df = (1 if n_docs < 3 else TFIDF_MIN_DF)
        vectorizer = TfidfVectorizer(
            max_df=max_df,
            min_df=min_df,
            ngram_range=TFIDF_NGRAM_RANGE,
            max_features=TFIDF_MAX_FEATURES,
            stop_words=stop_words,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z']{2,}\b",
        )
        tfidf = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()

        try:
            idx = ids.index(catalog_id)
        except ValueError:
            target_text = _sanitize_text_for_topics((catalog.content or "")[:MAX_CONTENT_LENGTH])
            corpus.insert(0, target_text)
            ids.insert(0, catalog_id)
            tfidf = vectorizer.fit_transform(corpus)
            feature_names = vectorizer.get_feature_names_out()
            idx = 0

        row = tfidf[idx].toarray().ravel()
        if row.size == 0:
            keywords = []
        else:
            top_idx = np.argsort(row)[::-1][:5]
            keywords = [feature_names[i].title() for i in top_idx if row[i] > 0]

        catalog.topics = keywords
        catalog.content_hash = content_hash
        catalog.topics_source_hash = content_hash
        db.commit()
        try:
            reindex_catalog(catalog_id)
        except Exception:
            pass

        return {"status": "complete", "topics": keywords}
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
