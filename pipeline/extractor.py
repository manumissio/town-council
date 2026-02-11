import os
import time
from tika import parser

from pipeline.models import Catalog
from pipeline.db_session import db_session
from pipeline.config import (
    TIKA_TIMEOUT_SECONDS,
    TIKA_RETRY_BACKOFF_MULTIPLIER,
    TIKA_OCR_FALLBACK_ENABLED,
    TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR,
    EXTRACTION_BATCH_SIZE
)

# Define where the Tika server is located (usually a separate Docker container)
TIKA_SERVER_ENDPOINT = os.getenv('TIKA_SERVER_ENDPOINT', 'http://tika:9998')

def is_safe_path(path):
    """
    Checks if a file path is safe to open.
    """
    # Use DATA_DIR from environment or default to local data folder
    base_dir = os.path.abspath(os.getenv('DATA_DIR', './data'))
    target_path = os.path.abspath(path)
    return target_path.startswith(base_dir)

def extract_text(file_path, *, ocr_fallback_enabled=None, min_chars_threshold=None):
    """
    Extracts text from a single file using Apache Tika.
    Inserts [PAGE X] markers for deep linking support.

    What this does:
    1. Sends the file to the Tika server (separate Docker container)
    2. Tika extracts text from PDF/HTML/DOC files
    3. Adds [PAGE X] markers so we can link directly to specific pages
    4. Retries with exponential backoff if Tika has temporary issues

    What is Apache Tika?
    An open-source library that extracts text and metadata from 1000+ file formats.
    Think of it as a universal document reader that works with PDFs, Word docs,
    HTML, images with text (OCR), and more.

    Why page markers?
    When a user searches for "bike lane" and finds a result on page 47 of a
    200-page packet, we want to jump them directly to page 47. The [PAGE 47]
    markers let us do this.
    """
    if not os.path.exists(file_path) or not is_safe_path(file_path):
        return ""

    def _tika_extract_with_strategy(ocr_strategy: str) -> str:
        """
        Extract XHTML via Tika using a specific OCR strategy.

        Strategy notes:
        - no_ocr: fast path, uses only the digital text layer.
        - ocr_only: slow path, runs OCR and ignores the digital layer.
        """
        # Retry logic with exponential backoff
        # Why retry? Tika server might be temporarily busy or restarting
        for attempt in range(3):
            try:
                headers = {
                    "X-Tika-PDFOcrStrategy": ocr_strategy,
                    "Accept": "application/xhtml+xml",
                }
                parsed = parser.from_file(
                    file_path,
                    serverEndpoint=TIKA_SERVER_ENDPOINT,
                    headers=headers,
                    requestOptions={"timeout": TIKA_TIMEOUT_SECONDS},
                )

                if parsed and "content" in parsed:
                    content = parsed["content"] or ""
                    if not content.strip():
                        raise ValueError("Tika returned empty XHTML content")

                    # Insert Page Markers
                    # Tika marks pages with <div class="page"> (XHTML) OR \f (form feed)
                    import re

                    if '<div class="page">' in content:
                        pages = re.split(r'<div[^>]*class="page"[^>]*>', content)
                    else:
                        pages = content.split("\f")

                    marked_content = ""
                    # pages[0] is usually boilerplate before the first page div
                    if len(pages) == 1:
                        clean_text = re.sub(r"<[^>]+>", "", pages[0]).strip()
                        marked_content = f"[PAGE 1]\n{clean_text}"
                    else:
                        for i, page_text in enumerate(pages):
                            if i == 0:
                                clean_text = re.sub(r"<[^>]+>", "", page_text).strip()
                                if clean_text:
                                    marked_content += clean_text + "\n"
                                continue

                            clean_page = re.sub(r"<[^>]+>", "", page_text).strip()
                            if clean_page:
                                marked_content += f"\n[PAGE {i}]\n{clean_page}\n"

                    return marked_content.strip()

                raise ValueError("Tika returned empty response")
            except (ValueError, OSError, ConnectionError, TimeoutError) as e:
                if attempt < 2:
                    wait_time = (attempt + 1) * TIKA_RETRY_BACKOFF_MULTIPLIER
                    print(
                        f"Tika issue on {file_path} (ocr_strategy={ocr_strategy}), retrying in {wait_time}s... "
                        f"(Attempt {attempt + 1}/3)"
                    )
                    time.sleep(wait_time)
                else:
                    print(f"Error extracting {file_path} (ocr_strategy={ocr_strategy}) after 3 attempts: {e}")
                    return ""
        return ""

    # Allow per-call overrides so async tasks can choose whether OCR fallback is enabled.
    # (We avoid mutating global module state or environment variables.)
    if ocr_fallback_enabled is None:
        ocr_fallback_enabled = TIKA_OCR_FALLBACK_ENABLED
    if min_chars_threshold is None:
        min_chars_threshold = TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR

    # Fast path: try digital text layer only.
    no_ocr_text = _tika_extract_with_strategy("no_ocr")
    if no_ocr_text and len(no_ocr_text) >= min_chars_threshold:
        return no_ocr_text

    # Slow fallback: if enabled and the digital layer was empty/too short, retry with OCR.
    if ocr_fallback_enabled:
        ocr_text = _tika_extract_with_strategy("ocr_only")
        return ocr_text or no_ocr_text

    return no_ocr_text

def extract_content():
    """
    Legacy batch function. Consider using run_pipeline.py instead.

    What this does:
    1. Finds all downloaded documents without extracted text
    2. Sends each document to Tika for text extraction
    3. Saves results in batches to the database

    Why batch commits?
    Committing after every document is slow (many database round-trips).
    Committing all at once is risky (if we crash, lose all progress).
    Batching strikes a balance: fast + safe progress checkpoints.

    What documents get processed?
    - Documents with a real file location (not 'placeholder')
    - Documents without content OR without page markers
      (Page markers were added later, so old documents need re-extraction)
    """
    # Use context manager for automatic session cleanup and error handling
    with db_session() as session:
        # Find documents that have been downloaded but don't have text extracted yet
        # OR documents that don't have the [PAGE ] marker yet
        from sqlalchemy import or_
        to_process = session.query(Catalog).filter(
            Catalog.location != 'placeholder',
            or_(
                Catalog.content == None,
                Catalog.content.notlike('%[PAGE %')
            )
        ).all()

        print(f"Found {len(to_process)} documents to process.")

        processed_count = 0

        # Process each document
        for record in to_process:
            print(f"Extracting text from: {record.filename}")

            # Extract text using Tika (can take 1-10 seconds per document)
            record.content = extract_text(record.location)
            processed_count += 1

            # Commit in batches for safety and performance
            # Why? If we crash halfway through, we don't lose all progress
            if processed_count % EXTRACTION_BATCH_SIZE == 0:
                session.commit()
                print(f"Committed batch of {EXTRACTION_BATCH_SIZE} records.")

        # Final commit for any remaining documents
        # The context manager will automatically rollback if this fails
        session.commit()
        print("Text extraction process complete.")

if __name__ == "__main__":
    print(f"Connecting to Tika server at {TIKA_SERVER_ENDPOINT}...")
    extract_content()
