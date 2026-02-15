"""
Pipeline Configuration Constants

What are "magic numbers"?
--------------------------
A "magic number" is a number in code that has no clear meaning. For example:

    BAD:  if len(text) > 50000:
          What is 50000? Why that number? Can I change it?

    GOOD: if len(text) > MAX_CONTENT_LENGTH:
          Clear meaning! I know what it's for and where to change it.

Why use constants?
------------------
1. **Readability**: Code is self-documenting
2. **Maintainability**: Change in one place, applies everywhere
3. **Consistency**: Same value used across all files
4. **Type Safety**: Can't accidentally type 5000 instead of 50000

How to use these constants:
----------------------------
    from pipeline.config import MAX_CONTENT_LENGTH

    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH]

All values in this file were extracted from the codebase where they appeared
as hardcoded numbers. Each constant includes a comment explaining its purpose.
"""

import os


# =============================================================================
# STARTUP PURGE CONFIGURATION
# =============================================================================
# These control whether derived data is automatically cleared when services boot.

# Enable derived-data purge during service startup.
# Disabled by default so non-dev environments stay safe unless explicitly enabled.
STARTUP_PURGE_DERIVED = os.getenv("STARTUP_PURGE_DERIVED", "false").strip().lower() in {"1", "true", "yes"}

# Runtime environment label used by startup safety guardrails.
APP_ENV = os.getenv("APP_ENV", "dev").strip().lower()

# Optional non-dev override.
STARTUP_PURGE_ALLOW_NON_DEV = os.getenv("STARTUP_PURGE_ALLOW_NON_DEV", "false").strip().lower() in {"1", "true", "yes"}

# =============================================================================
# CONTENT LENGTH LIMITS
# =============================================================================
# These control how much text we process to prevent memory issues

# Maximum length of content stored in Meilisearch search index (50KB of text)
# Why 50,000? Meilisearch performance degrades with very large documents
# Truncating here keeps search fast while preserving enough context
MAX_CONTENT_LENGTH = 50000

# Maximum text length for extractive summarization (50KB of text)
# The TextRank algorithm processes word relationships - too much text = slow
MAX_SUMMARY_TEXT_LENGTH = 50000

# Maximum text length for NLP entity extraction (100KB of text)
# SpaCy's NLP model can handle this much before memory becomes an issue
NLP_MAX_TEXT_LENGTH = 100000


# =============================================================================
# AI/LLM CONFIGURATION
# =============================================================================
# These control the local AI model behavior (Gemma 3 270M)

# =============================================================================
# LOCAL AI PROCESS MODEL GUARDRAILS
# =============================================================================
# LocalAI loads a llama.cpp GGUF model into the current *process*.
# Celery prefork/multiprocessing can spawn multiple worker processes, each loading its own model copy.
# These flags prevent accidental OOM by failing fast when LocalAI is used in a multiprocess worker.

LOCAL_AI_ALLOW_MULTIPROCESS = os.getenv("LOCAL_AI_ALLOW_MULTIPROCESS", "false").strip().lower() in {"1", "true", "yes"}
LOCAL_AI_REQUIRE_SOLO_POOL = os.getenv("LOCAL_AI_REQUIRE_SOLO_POOL", "true").strip().lower() in {"1", "true", "yes"}

# Context window size - how much text the model can "see" at once
# Default is conservative for Docker stability/perf. Gemma 3 270M supports up to 32K.
# Override via env when you want higher quality and can afford the extra KV cache.
LLM_CONTEXT_WINDOW = int(os.getenv("LLM_CONTEXT_WINDOW", "16384"))

# Maximum input text for summarization (chars).
# Char-based truncation is an approximation; we keep a buffer for prompt/response tokens.
LLM_SUMMARY_MAX_TEXT = int(os.getenv("LLM_SUMMARY_MAX_TEXT", "30000"))

# Maximum tokens in summary response.
# Slightly larger default helps avoid clipped narrative summaries.
LLM_SUMMARY_MAX_TOKENS = int(os.getenv("LLM_SUMMARY_MAX_TOKENS", "512"))

# Maximum input text for agenda extraction (chars).
# Larger than summary because we need enough context to see multiple items and headers.
LLM_AGENDA_MAX_TEXT = int(os.getenv("LLM_AGENDA_MAX_TEXT", "60000"))

# Maximum tokens in agenda response (1500 tokens ≈ 1125 words)
# Needs to be large enough to return 10-15 agenda items with descriptions
LLM_AGENDA_MAX_TOKENS = 1500

# Quality gates for AI-derived fields.
# These block generation when extracted text is too short/noisy to trust.
SUMMARY_MIN_CHARS = int(os.getenv("SUMMARY_MIN_CHARS", "80"))
SUMMARY_MIN_DISTINCT_TOKENS = int(os.getenv("SUMMARY_MIN_DISTINCT_TOKENS", "8"))
SUMMARY_MAX_BOILERPLATE_RATIO = float(os.getenv("SUMMARY_MAX_BOILERPLATE_RATIO", "0.85"))
TOPICS_MIN_CHARS = int(os.getenv("TOPICS_MIN_CHARS", "100"))
TOPICS_MIN_DISTINCT_TOKENS = int(os.getenv("TOPICS_MIN_DISTINCT_TOKENS", "10"))

# Minimum per-claim lexical support ratio used by the summary grounding check.
# 0.45 means nearly half of meaningful claim tokens must exist in source text.
SUMMARY_GROUNDING_MIN_COVERAGE = float(os.getenv("SUMMARY_GROUNDING_MIN_COVERAGE", "0.45"))


# =============================================================================
# FILE DOWNLOAD CONFIGURATION
# =============================================================================
# These control how PDFs are downloaded from city websites

# Maximum file size to download: 100MB
# Why? Most meeting packets are 5-20MB. 100MB catches outliers while
# preventing someone from uploading a 10GB file that crashes our system
MAX_FILE_SIZE_BYTES = 104857600  # 100 * 1024 * 1024

# Chunk size when writing downloaded files to disk: 8KB
# Files are written in small chunks to avoid loading entire PDF into memory
FILE_WRITE_CHUNK_SIZE = 8192

# Download timeout in seconds
# If a city's server doesn't respond in 30 seconds, give up and try later
DOWNLOAD_TIMEOUT_SECONDS = 30

# Number of parallel download workers
# How many PDFs we download simultaneously. 5 is polite to city servers.
DOWNLOAD_WORKERS = 5


# =============================================================================
# BATCH PROCESSING CONFIGURATION
# =============================================================================
# These control how many items we process at once

# Number of documents to send to Meilisearch in one batch
# Smaller batches = more network overhead, Larger batches = risk of timeout
# 20 is a sweet spot for fast indexing without overloading Meilisearch
MEILISEARCH_BATCH_SIZE = 20

# Number of documents to process in parallel during pipeline run
# Documents are split into chunks of this size for batch processing
# Each worker processes one chunk at a time with a single DB connection
DOCUMENT_CHUNK_SIZE = 20

# Maximum worker processes for parallel processing
# Prevents creating 100s of processes on high-core machines
# Capped at 5 to ensure Tika server stability with large PDF packets
MAX_WORKERS = 5

# CPU utilization fraction for parallel pipeline processing (0.75 = 75%)
# On a 4-core machine: 75% = 3 workers (but capped by MAX_WORKERS)
# Lower = more resources for other services, Higher = faster processing
PIPELINE_CPU_FRACTION = 0.75

# Retry delay range for database connection attempts (min, max seconds)
# Random delay prevents thundering herd when multiple workers retry simultaneously
DB_RETRY_DELAY_MIN = 1
DB_RETRY_DELAY_MAX = 3

# Batch size for agenda item extraction
# How many documents to process for agenda extraction in one batch
# Lower = faster feedback, Higher = more efficient database usage
AGENDA_BATCH_SIZE = 10

# Heuristic agenda-extraction safety limits (used when LLM extraction fails).
# These used to be hardcoded (3 items/page and 30 items/doc) which caused silent data loss.
# We keep them configurable and conservative to avoid runaway extraction on bad OCR.
AGENDA_FALLBACK_MAX_ITEMS_PER_DOC = int(os.getenv("AGENDA_FALLBACK_MAX_ITEMS_PER_DOC", "200"))
AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH = int(
    os.getenv("AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH", "25")
)
AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE = int(
    os.getenv("AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE", "15")
)

# Batch size for text extraction commits
# How many documents to extract before committing to database
# Smaller batches = more frequent saves, Larger batches = better performance
EXTRACTION_BATCH_SIZE = 10


# =============================================================================
# TIKA TEXT EXTRACTION CONFIGURATION
# =============================================================================
# These control how we extract text from PDFs and HTML files using Apache Tika

# Timeout for Tika server requests (in seconds)
# Tika can take time with large PDFs (OCR, complex layouts)
# 60 seconds handles most documents without hanging indefinitely
TIKA_TIMEOUT_SECONDS = 60

# Optional OCR fallback:
# - First attempt extracts the "digital text layer" only (fast).
# - If that result is empty/too small and OCR fallback is enabled, we retry with OCR.
#
# Why not OCR everything?
# OCR is much slower and CPU-heavy. Many PDFs already contain selectable text.
TIKA_OCR_FALLBACK_ENABLED = os.getenv("TIKA_OCR_FALLBACK_ENABLED", "false").strip().lower() in {"1", "true", "yes"}

# Minimum extracted characters to consider the digital text layer "good enough".
# If we extract fewer characters than this and OCR fallback is enabled, we retry with OCR.
TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR = int(os.getenv("TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR", "800"))

# Retry backoff multiplier for Tika requests
# When Tika fails, we wait (attempt × multiplier) seconds before retrying
# Attempt 1: wait 2s, Attempt 2: wait 4s
TIKA_RETRY_BACKOFF_MULTIPLIER = 2


# =============================================================================
# NLP & TOPIC MODELING CONFIGURATION
# =============================================================================
# These control how we extract topics and keywords from documents

# TF-IDF max document frequency (0.8 = 80%)
# Ignore words that appear in more than 80% of documents (like "meeting", "city")
# These common words don't help distinguish what makes each document unique
TFIDF_MAX_DF = 0.8

# TF-IDF min document frequency
# Allow words that appear in at least 1 document (captures unique topics)
# Higher values filter out rare words, but we want to catch even unique topics
TFIDF_MIN_DF = 1

# TF-IDF n-gram range (min, max)
# (1, 2) means we capture both single words ("Housing") and two-word phrases ("Rent Control")
# Single words alone miss important phrases, longer phrases are too rare
TFIDF_NGRAM_RANGE = (1, 2)

# Maximum features for TF-IDF vectorizer
# We keep the 5,000 most important words/phrases for topic analysis
# More = slower processing, Less = might miss important topics
TFIDF_MAX_FEATURES = 5000

# Number of top keywords to extract per document
# We identify the 5 most important keywords for each meeting
TOP_KEYWORDS_PER_DOC = 5

# Progress logging interval for batch operations
# Log progress every N documents to track processing without spamming logs
PROGRESS_LOG_INTERVAL = 50


# =============================================================================
# SIMILARITY & SEARCH CONFIGURATION
# =============================================================================
# These control how we find related documents

# Maximum content length for similarity analysis (5000 chars ≈ 1000 words)
# We use summaries when available, otherwise truncate content
# Shorter text = faster embedding generation without losing meaning
SIMILARITY_CONTENT_LENGTH = 5000

# Batch size for encoding embeddings (how many docs to process at once)
# 32 is optimal for sentence-transformers on CPU without GPU acceleration
# Larger batches = faster but more memory, smaller = slower but less memory
EMBEDDING_BATCH_SIZE = 32

# Similarity threshold for FAISS nearest neighbor search (0-1 scale)
# 0.35 = 35% similar. Documents must be at least this similar to be "related"
# Lower = more results but less relevant, Higher = fewer but more relevant
SIMILARITY_THRESHOLD = 0.35

# Number of nearest neighbors to fetch from FAISS index
# We get the top 4 most similar documents, then filter by threshold
FAISS_TOP_NEIGHBORS = 4

# Maximum related documents to display to users
# After filtering by threshold, show at most 3 related meetings
MAX_RELATED_DOCS = 3


# =============================================================================
# TABLE EXTRACTION CONFIGURATION
# =============================================================================
# These control PDF table extraction (Camelot library)

# Minimum accuracy threshold for table detection (0-100 scale)
# Only keep tables that Camelot is at least 70% confident about
# Lower = more false positives, Higher = might miss some real tables
TABLE_ACCURACY_MIN = 70

# Maximum pages to scan for tables in a single PDF
# Scanning full 500-page packets is slow, most tables are in first 5 pages
TABLE_SCAN_MAX_PAGES = 5

# CPU core fraction for table extraction workers (0.5 = 50% of cores)
# Table extraction is CPU-intensive. Using 50% keeps system responsive
# On a 4-core machine: 50% = 2 worker processes
TABLE_WORKER_CPU_FRACTION = 0.5

# Progress logging interval for table extraction
# Log progress every N documents processed
TABLE_PROGRESS_LOG_INTERVAL = 10
