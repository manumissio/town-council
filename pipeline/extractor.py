import os
import time
from tika import parser
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

# Define where the Tika server is located (usually a separate Docker container)
TIKA_SERVER_ENDPOINT = os.getenv('TIKA_SERVER_ENDPOINT', 'http://tika:9998')

def is_safe_path(path):
    """
    Checks if a file path is safe to open.
    
    Why this is needed:
    To prevent security vulnerabilities where a malicious path could trick the system
    into reading sensitive files outside the project directory (Path Traversal).
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    target_path = os.path.abspath(path)
    return target_path.startswith(base_dir)

def extract_content():
    """
    Finds downloaded documents (PDFs) that haven't been processed yet and
    extracts the raw text from them.
    
    How it works:
    1. It queries the database for files with no text content.
    2. It sends each file to the Apache Tika server (OCR/Extraction service).
    3. It saves the returned text back into the database.
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
        # Safety Check: Ensure the file actually exists and is in the allowed folder.
        if not os.path.exists(record.location) or not is_safe_path(record.location):
            print(f"Skipping unsafe or missing file: {record.location}")
            # Mark it as "empty" so we don't keep trying to process a broken file forever.
            record.content = ""
            continue

        print(f"Extracting text from: {record.filename}")
        
        try:
            # Send the file to Tika for processing.
            parsed = parser.from_file(record.location, serverEndpoint=TIKA_SERVER_ENDPOINT)
            
            if parsed and 'content' in parsed:
                text = parsed['content']
                # Save the extracted text (trimming extra whitespace).
                record.content = text.strip() if text else ""
                print(f"Successfully processed {record.filename}")
            else:
                print(f"Extraction failed for {record.filename}")
                record.content = ""

            processed_count += 1
            
            # Save progress every 10 files to avoid losing work if the script crashes.
            if processed_count % batch_size == 0:
                session.commit()
                print(f"Committed batch of {batch_size} records.")

        except Exception as e:
            print(f"Unexpected error with {record.filename}: {e}")
            session.rollback()

    # Final save for any remaining records.
    try:
        session.commit()
    except:
        session.rollback()
    
    session.close()
    print("Text extraction process complete.")

if __name__ == "__main__":
    print(f"Connecting to Tika server at {TIKA_SERVER_ENDPOINT}...")
    extract_content()
