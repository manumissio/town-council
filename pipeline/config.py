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

# Context window size - how much text the model can "see" at once
# 2048 tokens ≈ 1500 words, chosen for stability in Docker containers
LLM_CONTEXT_WINDOW = 2048

# Maximum input text for summarization (4000 chars ≈ 800 words)
# This fits comfortably in the context window with room for the response
LLM_SUMMARY_MAX_TEXT = 4000

# Maximum tokens in summary response (256 tokens ≈ 190 words)
# Limits response length to 3-4 bullet points as intended
LLM_SUMMARY_MAX_TOKENS = 256

# Maximum input text for agenda extraction (6000 chars ≈ 1200 words)
# Larger than summary because we need to see multiple agenda items at once
LLM_AGENDA_MAX_TEXT = 6000

# Maximum tokens in agenda response (1500 tokens ≈ 1125 words)
# Needs to be large enough to return 10-15 agenda items with descriptions
LLM_AGENDA_MAX_TOKENS = 1500


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
# This is multiplied by CPU count, so on a 4-core machine: 20 * 4 = 80 docs
DOCUMENT_CHUNK_SIZE = 20

# Maximum worker processes for parallel processing
# Prevents creating 100s of processes on high-core machines
MAX_WORKERS = 5


# =============================================================================
# NLP & TOPIC MODELING CONFIGURATION
# =============================================================================
# These control how we extract topics and keywords from documents

# TF-IDF max document frequency (0.8 = 80%)
# Ignore words that appear in more than 80% of documents (like "meeting", "city")
# These common words don't help distinguish what makes each document unique
TFIDF_MAX_DF = 0.8

# Maximum features for TF-IDF vectorizer
# We keep the 5,000 most important words/phrases for topic analysis
# More = slower processing, Less = might miss important topics
TFIDF_MAX_FEATURES = 5000

# Number of top keywords to extract per document
# We identify the 5 most important keywords for each meeting
TOP_KEYWORDS_PER_DOC = 5


# =============================================================================
# SIMILARITY & SEARCH CONFIGURATION
# =============================================================================
# These control how we find related documents

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
