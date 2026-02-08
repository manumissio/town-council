import os
import time
from tika import parser

from pipeline.models import Catalog
from pipeline.db_session import db_session
from pipeline.config import (
    TIKA_TIMEOUT_SECONDS,
    TIKA_RETRY_BACKOFF_MULTIPLIER,
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

def extract_text(file_path):
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

    # Retry logic with exponential backoff
    # Why retry? Tika server might be temporarily busy or restarting
    for attempt in range(3):
        try:
            # Request XHTML format to preserve page structure
            # "no_ocr" = don't do OCR (slow and expensive)
            # We only extract text from the digital layer
            headers = {
                "X-Tika-PDFOcrStrategy": "no_ocr",
                "Accept": "application/xhtml+xml"
            }

            # Send file to Tika server for processing
            parsed = parser.from_file(
                file_path,
                serverEndpoint=TIKA_SERVER_ENDPOINT,
                headers=headers,
                requestOptions={'timeout': TIKA_TIMEOUT_SECONDS}
            )

            if parsed and 'content' in parsed:
                content = parsed['content'] or ""

                # If it's empty, Tika might have failed to read the digital layer
                if not content.strip():
                     raise ValueError("Tika returned empty XHTML content")

                # Insert Page Markers
                # Tika marks pages with <div class="page"> (XHTML) OR \f (form feed)
                import re
                if '<div class="page">' in content:
                    # Split on page div tags
                    pages = re.split(r'<div[^>]*class="page"[^>]*>', content)
                else:
                    # Fallback: split on form feed character
                    pages = content.split('\f')

                marked_content = ""
                # pages[0] is usually boilerplate before the first page div
                if len(pages) == 1:
                    # Single page document, force a marker
                    clean_text = re.sub(r'<[^>]+>', '', pages[0]).strip()
                    marked_content = f"[PAGE 1]\n{clean_text}"
                else:
                    for i, page_text in enumerate(pages):
                        if i == 0:
                            # Strip HTML tags from initial boilerplate
                            clean_text = re.sub(r'<[^>]+>', '', page_text).strip()
                            if clean_text:
                                marked_content += clean_text + "\n"
                            continue

                        # Clean the page HTML (remove all tags)
                        clean_page = re.sub(r'<[^>]+>', '', page_text).strip()
                        if clean_page:
                            marked_content += f"\n[PAGE {i}]\n{clean_page}\n"

                return marked_content.strip()

            raise ValueError("Tika returned empty response")
        except (ValueError, OSError, ConnectionError, TimeoutError) as e:
            # Tika extraction errors: What can fail when calling the Tika server?
            # - ValueError: Tika returned empty content, or malformed response
            # - OSError: Local file doesn't exist or can't be read
            # - ConnectionError: Can't reach Tika server (network down, wrong URL)
            # - TimeoutError: Tika took too long (large/complex PDF)
            # Why retry with exponential backoff?
            #   Tika might be temporarily overloaded or restarting
            #   Waiting longer between retries gives it time to recover
            if attempt < 2:
                # Exponential backoff: wait longer each retry
                # Attempt 1: wait 2s, Attempt 2: wait 4s
                wait_time = (attempt + 1) * TIKA_RETRY_BACKOFF_MULTIPLIER
                print(f"Tika issue on {file_path}, retrying in {wait_time}s... (Attempt {attempt+1}/3)")
                time.sleep(wait_time)
            else:
                print(f"Error extracting {file_path} after 3 attempts: {e}")
                return ""
    return ""

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
