from celery import Celery
from celery.signals import worker_ready
import os
import sys
import logging
import re
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import db_connect, Catalog, Document
from pipeline.llm import LocalAI, LocalAIConfigError
from pipeline.agenda_service import persist_agenda_items
from pipeline.agenda_resolver import resolve_agenda_items
from pipeline.models import AgendaItem
from pipeline.config import (
    TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
    LOCAL_AI_ALLOW_MULTIPROCESS,
    LOCAL_AI_REQUIRE_SOLO_POOL,
    ENABLE_VOTE_EXTRACTION,
    AGENDA_SUMMARY_MAX_INPUT_CHARS,
    AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS,
)
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
from pipeline.vote_extractor import run_vote_extraction_for_catalog

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


def _get_celery_pool_from_argv(argv: list[str]) -> str | None:
    """
    Best-effort extraction of the Celery pool from argv.

    Why this exists:
    Celery's "sender" object passed to worker_ready isn't guaranteed to expose pool
    details across versions/configs, but argv is stable for our Docker entrypoint.
    """
    if not argv:
        return None
    for i, arg in enumerate(argv):
        if arg.startswith("--pool="):
            return arg.split("=", 1)[1].strip() or None
        if arg == "--pool" and (i + 1) < len(argv):
            return (argv[i + 1] or "").strip() or None
    return None


@worker_ready.connect
def _run_startup_purge_on_worker_ready(sender=None, **kwargs):
    # Guardrail: LocalAI's singleton is per-process. If a worker is configured with
    # concurrency > 1 (or a multiprocessing pool), each process will load its own model.
    # This can OOM a dev machine quickly.
    try:
        concurrency = getattr(sender, "concurrency", None)
        if concurrency is None and sender is not None:
            concurrency = getattr(getattr(sender, "app", None), "conf", {}).get("worker_concurrency")  # type: ignore[attr-defined]
        pool = _get_celery_pool_from_argv(getattr(sender, "argv", None) or sys.argv)  # type: ignore[arg-type]

        if not LOCAL_AI_ALLOW_MULTIPROCESS:
            # Default stance: LocalAI runs in-process via llama.cpp, which loads the model
            # into the current process's RAM. Multiprocess pools will duplicate the model.
            if LOCAL_AI_REQUIRE_SOLO_POOL and pool and pool != "solo":
                logger.critical(
                    "Unsafe worker pool for LocalAI: pool=%s. "
                    "Run Celery with --pool=solo (and typically --concurrency=1), or use an inference server backend.",
                    pool,
                )
                raise SystemExit(1)
            if isinstance(concurrency, int) and concurrency > 1 and (pool is None or pool != "solo"):
                logger.critical(
                    "Unsafe worker concurrency for LocalAI: concurrency=%s pool=%s. "
                    "Run Celery with --concurrency=1 --pool=solo, or use an inference server backend.",
                    concurrency,
                    pool,
                )
                raise SystemExit(1)
    except SystemExit:
        raise
    except Exception:
        pass

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
        
        # Decide how to summarize based on the *document type*.
        # Many cities publish agenda PDFs without corresponding minutes PDFs.
        # If we summarize an agenda using a "minutes" prompt, the output looks incorrect.
        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        doc_kind = (doc.category or "unknown") if doc else "unknown"

        if not catalog:
            return {"error": "Catalog not found"}

        # Ensure we have a stable fingerprint for "is this summary stale?"
        content_hash = compute_content_hash(catalog.content) if (catalog.content or "") else None
        if content_hash:
            catalog.content_hash = content_hash

        # Minutes/unknown summaries are grounded in extracted text, so we block low-signal inputs.
        # Agenda summaries are derived from segmented agenda items, so the extracted-text quality
        # gate is not the right control (Legistar items can be good even if PDF text is sparse).
        if doc_kind != "agenda":
            if not catalog.content:
                return {"error": "No content to summarize"}
            quality = analyze_source_text(catalog.content)
            if not is_source_summarizable(quality):
                # We do not run Gemma on low-signal content because it tends to hallucinate.
                return {
                    "status": "blocked_low_signal",
                    "reason": build_low_signal_message(quality),
                    "summary": None,
                }
        
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

        # Agenda summaries are derived from segmented agenda items (not raw PDF text) so the
        # AI Summary and Structured Agenda tabs cannot drift.
        # Whether we should run the "summary must be lexically grounded in extracted text" check.
        # Agenda summaries are derived from structured items, so we do not ground against the PDF text.
        do_grounding_check = True
        if doc_kind == "agenda":
            # Agenda summaries must be derived from segmented agenda items so the
            # AI Summary and Structured Agenda tabs cannot drift.
            existing_items = (
                db.query(AgendaItem)
                .filter_by(catalog_id=catalog_id)
                .order_by(AgendaItem.order)
                .all()
            )
            if not existing_items:
                return {
                    "status": "not_generated_yet",
                    "reason": "Agenda summary requires segmented agenda items. Run segmentation first.",
                    "summary": None,
                }

            # Filter obvious boilerplate titles defensively in case old polluted rows exist.
            from pipeline.llm import _looks_like_agenda_segmentation_boilerplate, _should_drop_from_agenda_summary
            summary_items = []
            candidate_items_total = 0
            input_chars = 0
            max_input_chars = max(1000, AGENDA_SUMMARY_MAX_INPUT_CHARS - AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS)
            # Why this branch exists: we must cap prompt size to avoid llama.cpp context overflow
            # when councils publish many long agenda descriptions.
            for it in existing_items:
                title = (it.title or "").strip()
                if not title:
                    continue
                if _looks_like_agenda_segmentation_boilerplate(title):
                    continue
                description = (it.description or "").strip()
                serialized = title if not description else f"{title} - {description}"
                if _should_drop_from_agenda_summary(serialized):
                    continue
                candidate_items_total += 1
                item_payload = {
                    "title": title,
                    "description": description,
                    "classification": (it.classification or "").strip(),
                    "result": (it.result or "").strip(),
                    "page_number": int(it.page_number or 0),
                }
                item_block = (
                    f"Title: {item_payload['title']}\n"
                    f"Description: {item_payload['description']}\n"
                    f"Classification: {item_payload['classification']}\n"
                    f"Result: {item_payload['result']}\n"
                    f"Page: {item_payload['page_number']}\n\n"
                )
                if (input_chars + len(item_block)) > max_input_chars:
                    break
                summary_items.append(item_payload)
                input_chars += len(item_block)

            if not summary_items:
                return {
                    "status": "blocked_low_signal",
                    "reason": "No substantive agenda items detected after boilerplate filtering. Re-segment the agenda.",
                    "summary": None,
                }

            # Use all available titles, bounded only by model context. If we must truncate,
            # we disclose it in the prompt requirements.
            summary = local_ai.summarize_agenda_items(
                meeting_title=(doc.event.name if doc and doc.event and doc.event.name else ""),
                meeting_date=(str(doc.event.record_date) if doc and doc.event and doc.event.record_date else ""),
                items=summary_items,
                truncation_meta={
                    "items_total": candidate_items_total,
                    "items_included": len(summary_items),
                    "items_truncated": max(0, candidate_items_total - len(summary_items)),
                    "input_chars": input_chars,
                },
            )
            # Agenda summaries are derived from structured titles, not raw text.
            do_grounding_check = False
        else:
            summary = local_ai.summarize(postprocess_extracted_text(catalog.content), doc_kind=doc_kind)
        
        # Retry instead of storing an empty summary.
        if summary is None:
            raise RuntimeError("AI Summarization returned None (Model missing or error)")

        # Guardrail: block ungrounded model claims (deterministic agenda-title summaries are exempt).
        if do_grounding_check:
            # Ground against the extracted text. This is conservative and may block on
            # paraphrases; if it becomes too strict for agenda-item summaries, we can
            # switch to grounding against the agenda-items payload instead.
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
        if content_hash:
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

    except LocalAIConfigError as e:
        # Configuration errors are not transient; do not retry.
        logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        return {"status": "error", "error": str(e)}
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
        vote_extraction = {
            "status": "disabled",
            "processed_items": 0,
            "updated_items": 0,
            "skipped_items": 0,
            "failed_items": 0,
            "skip_reasons": {},
        }
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

            # Vote/outcome extraction is a separate post-segmentation stage.
            # Keep segmentation successful even if vote extraction later fails.
            if ENABLE_VOTE_EXTRACTION:
                try:
                    vote_counters = run_vote_extraction_for_catalog(
                        db,
                        local_ai,
                        catalog,
                        doc,
                        force=False,
                        agenda_items=created_items,
                    )
                    vote_extraction = {"status": "complete", **vote_counters}
                except Exception as vote_exc:
                    logger.warning(
                        "vote_extraction.post_segment_failed catalog_id=%s error=%s",
                        catalog_id,
                        vote_exc.__class__.__name__,
                    )
                    vote_extraction = {
                        "status": "failed",
                        "error": vote_exc.__class__.__name__,
                        "processed_items": 0,
                        "updated_items": 0,
                        "skipped_items": 0,
                        "failed_items": 0,
                        "skip_reasons": {},
                    }
            
            catalog.agenda_segmentation_status = "complete"
            catalog.agenda_segmentation_item_count = count
            catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
            catalog.agenda_segmentation_error = None
            db.commit()
        else:
            # Terminal state: agenda segmentation ran but found no substantive items.
            catalog.agenda_segmentation_status = "empty"
            catalog.agenda_segmentation_item_count = 0
            catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
            catalog.agenda_segmentation_error = None
            db.commit()
            vote_extraction = {
                "status": "skipped_no_items",
                "processed_items": 0,
                "updated_items": 0,
                "skipped_items": 0,
                "failed_items": 0,
                "skip_reasons": {},
            }
            
        logger.info(f"Segmentation complete: {count} items found (source={resolved['source_used']})")
        return {
            "status": "complete",
            "item_count": count,
            "items": items_to_return,
            "source_used": resolved["source_used"],
            "quality_score": resolved["quality_score"],
            "vote_extraction": vote_extraction,
        }

    except LocalAIConfigError as e:
        logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        try:
            catalog = db.get(Catalog, catalog_id)
            if catalog:
                catalog.agenda_segmentation_status = "failed"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = str(e)[:500]
                db.commit()
        except Exception:
            db.rollback()
        return {"status": "error", "error": str(e)}
    except (SQLAlchemyError, RuntimeError, KeyError, ValueError) as e:
        logger.error(f"Task failed: {e}")
        db.rollback()
        # Best-effort: persist failure status so batch workers don't spin forever.
        try:
            catalog = db.get(Catalog, catalog_id)
            if catalog:
                catalog.agenda_segmentation_status = "failed"
                catalog.agenda_segmentation_item_count = 0
                catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
                catalog.agenda_segmentation_error = str(e)[:500]
                db.commit()
        except Exception:
            db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(bind=True, max_retries=3)
def extract_votes_task(self, catalog_id: int, force: bool = False):
    """
    Background task: extract agenda-item outcomes/vote tallies from catalog text.
    """
    db = SessionLocal()
    local_ai = LocalAI()

    try:
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            return {"error": "Catalog not found"}

        doc = db.query(Document).filter_by(catalog_id=catalog_id).first()
        if not doc:
            return {"error": "Document not linked to catalog"}

        if not ENABLE_VOTE_EXTRACTION and not force:
            return {
                "status": "disabled",
                "reason": "Vote extraction is disabled. Set ENABLE_VOTE_EXTRACTION=true or run with force=true.",
                "processed_items": 0,
                "updated_items": 0,
                "skipped_items": 0,
                "failed_items": 0,
                "skip_reasons": {},
            }

        existing_items = (
            db.query(AgendaItem)
            .filter_by(catalog_id=catalog_id)
            .order_by(AgendaItem.order)
            .all()
        )
        if not existing_items:
            return {
                "status": "not_generated_yet",
                "reason": "Vote extraction requires segmented agenda items. Run segmentation first.",
                "processed_items": 0,
                "updated_items": 0,
                "skipped_items": 0,
                "failed_items": 0,
                "skip_reasons": {},
            }

        counters = run_vote_extraction_for_catalog(
            db,
            local_ai,
            catalog,
            doc,
            force=force,
            agenda_items=existing_items,
        )
        db.commit()

        try:
            reindex_catalog(catalog_id)
        except Exception:
            pass

        return {"status": "complete", **counters}
    except LocalAIConfigError as e:
        logger.critical(f"LocalAI misconfiguration: {e}")
        db.rollback()
        return {"status": "error", "error": str(e)}
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        logger.error(f"Vote extraction task failed: {e}")
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
