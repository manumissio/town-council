from celery import Celery
from celery.signals import worker_ready
import os
import logging
import re
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import db_connect, Catalog, Document
from pipeline.llm import LocalAI
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import resolve_agenda_items
from pipeline.models import AgendaItem
from pipeline.config import TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR
from pipeline.extraction_service import reextract_catalog_content
from pipeline.indexer import reindex_catalog
from pipeline.content_hash import compute_content_hash
from pipeline.summary_quality import (
    analyze_source_text,
    build_low_signal_message,
    is_source_summarizable,
    is_source_topicable,
    is_summary_grounded,
)
from pipeline.text_cleaning import postprocess_extracted_text
from pipeline.startup_purge import run_startup_purge_if_enabled

# Register worker metrics (safe in non-worker contexts; the HTTP server only starts
# when TC_WORKER_METRICS_PORT is set and the Celery worker is ready).
from pipeline import metrics as _worker_metrics  # noqa: F401

# Setup logging
logger = logging.getLogger("celery-worker")


def _dedupe_titles_preserve_order(values):
    """
    Deduplicate extracted title candidates without reordering them.
    """
    seen = set()
    out = []
    for v in values or []:
        key = (v or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v.strip())
    return out


def _extract_agenda_titles_from_text(text: str, max_titles: int = 3):
    """
    Best-effort agenda title extraction from raw/flattened extracted text.

    Why this exists:
    Some "agenda" PDFs are tiny, header-heavy, or flattened into a single line.
    In those cases, an LLM summary often degenerates into boilerplate or headings.
    This heuristic keeps the output deterministic and city-agnostic.
    """
    if not text:
        return []

    # Page markers are useful for deep linking, but they make regex parsing noisier.
    value = re.sub(r"\[PAGE\s+\d+\]", "\n", text, flags=re.IGNORECASE)
    # Normalize runs of spaces/tabs without deleting letters.
    value = re.sub(r"[ \t]+", " ", value)

    titles = []

    def _looks_like_attendance_or_access_info(line: str) -> bool:
        """
        Skip "how to attend" boilerplate.

        Why:
        Many agendas include numbered participation instructions (email/phone/webinar).
        Those are not agenda *items* and should not drive summaries.
        """
        v = (line or "").strip().lower()
        if not v:
            return True
        needles = [
            "teleconference",
            "public participation",
            "email comments",
            "e-mail comments",
            "email address",
            "enter an email",
            "enter your email",
            "register",
            "webinar",
            "zoom",
            "webex",
            "teams",
            "passcode",
            "phone",
            "dial",
            "raise hand",
            "unmute",
            "mute",
            "last four digits",
            "time allotted",
            "limit your remarks",
            "browser",
            "microsoft edge",
            "internet explorer",
            "safari",
            "firefox",
            "chrome",
            "ada",
            "accommodation",
            "accessibility",
        ]
        return any(n in v for n in needles)

    # 1) Prefer true line-based numbering when available.
    for m in re.finditer(r"(?m)^\s*\d+\.\s+(.+?)\s*$", value):
        title = (m.group(1) or "").strip()
        if not title or len(title) < 10:
            continue
        if _looks_like_attendance_or_access_info(title):
            continue
        titles.append(title)
        if len(titles) >= max_titles:
            break

    # 2) Fallback: split by inline numbering when extraction collapsed line breaks.
    if len(titles) < max_titles:
        parts = re.split(r"\b(\d{1,2})\.\s+", value)
        # parts: [prefix, num, rest, num, rest, ...]
        for i in range(1, len(parts), 2):
            rest = (parts[i + 1] if i + 1 < len(parts) else "").strip()
            if not rest:
                continue
            candidate = rest.split("\n", 1)[0].strip()
            candidate = candidate[:160].strip()
            if len(candidate) < 10:
                continue
            if _looks_like_attendance_or_access_info(candidate):
                continue
            titles.append(candidate)
            if len(titles) >= max_titles:
                break

    return _dedupe_titles_preserve_order(titles)[:max_titles]

# Celery broker queues tasks; result backend stores task results.
app = Celery('tasks')

# Read connection settings from environment.
app.conf.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Database Setup
engine = db_connect()
SessionLocal = sessionmaker(bind=engine)


@worker_ready.connect
def _run_startup_purge_on_worker_ready(sender=None, **kwargs):
    # The purge is env-gated and DB-lock protected so concurrent starters are safe.
    result = run_startup_purge_if_enabled()
    logger.info(f"startup_purge_result={result}")

@app.task(bind=True, max_retries=3)
def generate_summary_task(self, catalog_id: int, force: bool = False):
    """
    Background task: generate and store a catalog summary.
    """
    db = SessionLocal()
    local_ai = LocalAI()
    
    try:
        logger.info(f"Starting summarization for Catalog ID {catalog_id}")
        catalog = db.get(Catalog, catalog_id)
        
        if not catalog or not catalog.content:
            return {"error": "No content to summarize"}

        # Ensure we have a stable fingerprint for "is this summary stale?"
        content_hash = catalog.content_hash or compute_content_hash(catalog.content)
        quality = analyze_source_text(catalog.content)
        if not is_source_summarizable(quality):
            # We do not run Gemma on low-signal content because it tends to hallucinate.
            return {
                "status": "blocked_low_signal",
                "reason": build_low_signal_message(quality),
                "summary": None,
            }

        # Decide how to summarize based on the *document type*.
        # Many cities publish agenda PDFs without corresponding minutes PDFs.
        # If we summarize an agenda using a "minutes" prompt, the output looks incorrect.
        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        doc_kind = (doc.category or "unknown") if doc else "unknown"
        
        # Return cached value when already summarized, unless the caller forces a refresh.
        #
        # Why have `force`?
        # Summaries are cached on the Catalog row. When we improve the prompt/cleanup logic,
        # old low-quality summaries won't change unless we regenerate them.
        is_fresh = bool(
            catalog.summary
            and content_hash
            and catalog.summary_source_hash
            and catalog.summary_source_hash == content_hash
        )
        if (not force) and is_fresh:
            return {"status": "cached", "summary": catalog.summary}
        if (not force) and catalog.summary and not is_fresh:
            # Keep the old summary visible, but mark it as out-of-date.
            return {"status": "stale", "summary": catalog.summary}

        # If agenda items already exist, prefer a deterministic agenda-style summary instead
        # of relying entirely on the LLM. This is fast, stable, and avoids "how to attend"
        # boilerplate dominating the output.
        #
        # This is intentionally simple: we list the first few agenda item titles in order.
        used_model_summary = True
        if doc_kind == "agenda":
            existing_items = (
                db.query(AgendaItem)
                .filter_by(catalog_id=catalog_id)
                .order_by(AgendaItem.order)
                .limit(6)
                .all()
            )
            if existing_items:
                titles = [it.title.strip() for it in existing_items if it.title and it.title.strip()]
                titles = titles[:3]
                if titles:
                    # Keep summary format consistent: BLUF + plain-text bullets (no Markdown).
                    bluf = f"BLUF: Agenda covers {len(existing_items)} main items."
                    summary = "\n".join([bluf] + [f"- {t}" for t in titles])
                    used_model_summary = False
                else:
                    summary = local_ai.summarize(postprocess_extracted_text(catalog.content), doc_kind=doc_kind)
            else:
                # Fallback: try to extract a few agenda titles directly from the text before invoking the model.
                cleaned = postprocess_extracted_text(catalog.content)
                title_matches = _extract_agenda_titles_from_text(cleaned, max_titles=3)
                if title_matches:
                    bluf = f"BLUF: Agenda covers {len(title_matches)} highlighted items."
                    summary = "\n".join([bluf] + [f"- {t}" for t in title_matches])
                    used_model_summary = False
                else:
                    summary = local_ai.summarize(cleaned, doc_kind=doc_kind)
        else:
            summary = local_ai.summarize(postprocess_extracted_text(catalog.content), doc_kind=doc_kind)
        
        # Retry instead of storing an empty summary.
        if summary is None:
            raise RuntimeError("AI Summarization returned None (Model missing or error)")

        # Guardrail: block ungrounded model claims (deterministic agenda-title summaries are exempt).
        if used_model_summary:
            grounding = is_summary_grounded(summary, postprocess_extracted_text(catalog.content))
            if not grounding.is_grounded:
                reason = (
                    "Generated summary appears unsupported by extracted text. "
                    f"(coverage={grounding.coverage:.2f})"
                )
                return {
                    "status": "blocked_ungrounded",
                    "reason": reason,
                    "unsupported_claims": grounding.unsupported_claims[:3],
                    "summary": None,
                }
        
        # Update DB
        catalog.summary = summary
        catalog.content_hash = content_hash
        catalog.summary_source_hash = content_hash
        db.commit()

        # Best-effort: update the search index for just this catalog so stale flags
        # and snippets stay in sync for future searches.
        try:
            reindex_catalog(catalog_id)
        except Exception:
            pass
        
        logger.info(f"Summarization complete for Catalog ID {catalog_id}")
        return {"status": "complete", "summary": summary}

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
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
            # We keep existing topics untouched and ask the user to improve extraction first.
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

        # Reuse the same sanitation rules as the batch topic worker.
        from pipeline.topic_worker import _sanitize_text_for_topics
        from pipeline.config import (
            MAX_CONTENT_LENGTH,
            TFIDF_MAX_DF,
            TFIDF_MIN_DF,
            TFIDF_NGRAM_RANGE,
            TFIDF_MAX_FEATURES,
        )
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        import numpy as np

        # Build a bounded, same-city corpus so TF-IDF weights are meaningful but fast.
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
        # If sanitation removed everything (e.g., doc was all URLs/page markers), TF-IDF can't work.
        if not any(s.strip() for s in corpus):
            return {
                "status": "blocked_low_signal",
                "reason": "Not enough usable text to generate topics.",
                "topics": [],
            }

        # Use the same municipal stopwords as the batch worker so we don't emit date tokens
        # like "September" or URL fragments as "topics".
        from pipeline.topic_worker import CITY_STOP_WORDS

        # City names are already visible in the UI metadata, so they tend to be "decorative"
        # topics. Remove place tokens to let actual subject matter rise to the top.
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
            # With only 1-2 documents, TF-IDF is either unstable or just returns generic words.
            # Use a deterministic single-document fallback that favors agenda "Subject:" lines.
            cleaned = postprocess_extracted_text(catalog.content)
            titles = _extract_agenda_titles_from_text(cleaned, max_titles=8)
            if titles:
                # Strip common template labels and "(Presenter)" suffixes.
                normalized_titles = []
                for t in titles:
                    v = re.sub(r"\([^)]*\)", " ", t)  # drop presenter/staff name suffix
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

            # Prefer short phrases (bigrams/trigrams) over single words.
            phrase_counts = {}
            for n in (3, 2):
                for i in range(0, max(0, len(filtered) - n + 1)):
                    phrase = " ".join(filtered[i : i + n])
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

            unigram_counts = {}
            for t in filtered:
                unigram_counts[t] = unigram_counts.get(t, 0) + 1

            ranked_phrases = sorted(phrase_counts.items(), key=lambda kv: (-kv[1], kv[0]))
            ranked_unigrams = sorted(unigram_counts.items(), key=lambda kv: (-kv[1], kv[0]))

            keywords = []
            seen = set()
            for phrase, _n in ranked_phrases:
                key = phrase.lower()
                if key in seen:
                    continue
                seen.add(key)
                keywords.append(phrase.title())
                if len(keywords) >= 5:
                    break
            if len(keywords) < 5:
                for word, _n in ranked_unigrams:
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
            # When a city has very few extracted documents, scikit can throw:
            # "max_df corresponds to < documents than min_df".
            # Use min_df=1/max_df=1.0 for tiny corpora so per-catalog topic regeneration still works.
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
            # The target doc might be older than our corpus window; include it explicitly.
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
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

@app.task(bind=True, max_retries=3)
def segment_agenda_task(self, catalog_id: int):
    """
    Background task: segment catalog text into agenda items.
    """
    db = SessionLocal()
    local_ai = LocalAI()
    
    try:
        logger.info(f"Starting segmentation for Catalog ID {catalog_id}")
        catalog = db.get(Catalog, catalog_id)
        
        if not catalog or not catalog.content:
            return {"error": "No content"}
            
        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return {"error": "Document not linked to event"}
            
        resolved = resolve_agenda_items(db, catalog, doc, local_ai)
        items_data = resolved["items"]
        
        count = 0
        items_to_return = []
        if items_data:
            created_items = persist_agenda_items(db, catalog_id, doc.event_id, items_data)
            for item in created_items:
                items_to_return.append({
                    "title": item.title,
                    "description": item.description,
                    "order": item.order,
                    "classification": item.classification,
                    "result": item.result,
                    "page_number": item.page_number,
                    "source": resolved["source_used"],
                })
                count += 1
            
            db.commit()
            
        logger.info(f"Segmentation complete: {count} items found (source={resolved['source_used']})")
        return {
            "status": "complete",
            "item_count": count,
            "items": items_to_return,
            "source_used": resolved["source_used"],
            "quality_score": resolved["quality_score"],
        }

    except (SQLAlchemyError, RuntimeError, KeyError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def extract_text_task(self, catalog_id: int, force: bool = False, ocr_fallback: bool = False):
    """
    Background task: re-extract a catalog's text from the already-downloaded file.

    This is intentionally "no download" and single-catalog scoped:
    - It only reads Catalog.location on disk.
    - It updates Catalog.content in the DB.
    - It reindexes just this catalog into Meilisearch.
    """
    db = SessionLocal()
    try:
        catalog = db.get(Catalog, catalog_id)
        result = reextract_catalog_content(
            catalog,
            force=force,
            ocr_fallback=ocr_fallback,
            min_chars=TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
        )
        if "error" in result:
            # Only retry for transient extraction failures. Missing files / unsafe paths
            # should return immediately so the user can take action.
            transient = result["error"].lower() in {
                "extraction returned empty text",
            }
            if transient:
                raise RuntimeError(result["error"])
            return result

        db.commit()

        # Best-effort: update the search index for just this catalog.
        try:
            reindex_catalog(catalog_id)
        except Exception as e:
            # If reindexing fails, keep the extracted text (DB is source of truth).
            return {**result, "reindex_error": str(e)}

        return result
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()
