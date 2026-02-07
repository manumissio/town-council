import os
import time
from tika import parser
from sqlalchemy.orm import sessionmaker
from pipeline.models import Catalog, db_connect, create_tables

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
    Extracts text from a single file using Tika.
    Includes a 3-attempt retry loop for stability.
    """
    if not os.path.exists(file_path) or not is_safe_path(file_path):
        return ""
        
    for attempt in range(3):
        try:
            # PERFORMANCE: We disable OCR because these PDFs are 'Born Digital'.
            # This is 100x faster and prevents Tika from crashing on large files.
            headers = {
                "X-Tika-PDFOcrStrategy": "no_ocr",
                "Accept": "text/plain"
            }
            
            # 60 seconds is plenty for a text-only read
            parsed = parser.from_file(
                file_path, 
                serverEndpoint=TIKA_SERVER_ENDPOINT, 
                headers=headers,
                requestOptions={'timeout': 60}
            )
            
            if parsed and 'content' in parsed:
                return (parsed['content'] or "").strip()
            
            # If we get here, Tika likely returned a 503 or empty result.
            # We raise an error to trigger our retry logic.
            raise ValueError("Tika returned empty content or 503 error")
        except Exception as e:
            if attempt < 2:
                # Exponential backoff (2s, 4s)
                wait_time = (attempt + 1) * 2
                print(f"Tika issue on {file_path}, retrying in {wait_time}s... (Attempt {attempt+1}/3)")
                time.sleep(wait_time)
            else:
                print(f"Error extracting {file_path} after 3 attempts: {e}")
                return ""
    return ""

def extract_content():
    """
    Legacy batch function. Consider using run_pipeline.py instead.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that have been downloaded but don't have text extracted yet.
    to_process = session.query(Catalog).filter(
        Catalog.location != 'placeholder',
        Catalog.content == None
    ).all()

    print(f"Found {len(to_process)} documents to process.")

    batch_size = 10
    processed_count = 0

    for record in to_process:
        print(f"Extracting text from: {record.filename}")
        
        record.content = extract_text(record.location)
        processed_count += 1
            
        if processed_count % batch_size == 0:
            session.commit()
            print(f"Committed batch of {batch_size} records.")

    session.commit()
    session.close()
    print("Text extraction process complete.")

if __name__ == "__main__":
    print(f"Connecting to Tika server at {TIKA_SERVER_ENDPOINT}...")
    extract_content()
