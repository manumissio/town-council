import os
import time
from tika import parser
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

# Define where the Tika server is located
TIKA_SERVER_ENDPOINT = os.getenv('TIKA_SERVER_ENDPOINT', 'http://tika:9998')

def is_safe_path(path):
    """
    Ensures the file path is actually inside our designated data directory.
    This is a safety check to prevent reading files from other parts of the system.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    target_path = os.path.abspath(path)
    return target_path.startswith(base_dir)

def extract_content():
    """
    Scans the database for downloaded documents that haven't had their text extracted yet.
    Sends them to Apache Tika for processing and saves the results.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Select records that have a file location but no content yet
    to_process = session.query(Catalog).filter(
        Catalog.location != 'placeholder',
        Catalog.content == None
    ).all()

    print(f"Found {len(to_process)} documents to process.")

    batch_size = 10
    processed_count = 0

    for record in to_process:
        # Verify the file exists and is in a safe location before reading
        if not os.path.exists(record.location) or not is_safe_path(record.location):
            print(f"Skipping unsafe or missing file: {record.location}")
            # Mark as processed with empty string so we don't keep retrying it
            record.content = ""
            continue

        print(f"Extracting text from: {record.filename}")
        
        try:
            # Request text extraction. serverEndpoint must be passed as a keyword argument.
            parsed = parser.from_file(record.location, serverEndpoint=TIKA_SERVER_ENDPOINT)
            
            if parsed and 'content' in parsed:
                text = parsed['content']
                # Store the text, or an empty string if nothing was found
                record.content = text.strip() if text else ""
                print(f"Successfully processed {record.filename}")
            else:
                print(f"Extraction failed for {record.filename}")
                record.content = ""

            processed_count += 1
            
            # Commit changes in batches to improve database performance
            if processed_count % batch_size == 0:
                session.commit()
                print(f"Committed batch of {batch_size} records.")

        except Exception as e:
            print(f"Unexpected error with {record.filename}: {e}")
            session.rollback()

    # Final commit for any remaining records
    try:
        session.commit()
    except:
        session.rollback()
    
    session.close()
    print("Text extraction process complete.")

if __name__ == "__main__":
    # Small delay to ensure the Tika container has fully initialized if starting together
    print(f"Connecting to Tika server at {TIKA_SERVER_ENDPOINT}...")
    extract_content()