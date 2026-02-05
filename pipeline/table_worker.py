import os
import camelot
import json
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

def extract_tables():
    """
    Scans for downloaded PDFs that haven't had tables extracted yet.
    Uses Camelot to detect and extract tabular data into structured JSON.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that have been downloaded but no tables extracted
    # (Checking if tables is NULL)
    to_process = session.query(Catalog).filter(
        Catalog.location != 'placeholder',
        Catalog.tables == None
    ).all()

    print(f"Found {len(to_process)} documents for table extraction.")

    for record in to_process:
        if not os.path.exists(record.location):
            print(f"Skipping missing file: {record.location}")
            record.tables = [] # Mark as processed
            continue

        # Only process PDFs
        if not record.filename.lower().endswith('.pdf'):
            record.tables = []
            continue

        print(f"Extracting tables from: {record.filename}")
        
        try:
            # PERFORMANCE: Limit to first 20 pages to avoid hanging on massive reports.
            # 'lattice' mode is best for tables with grid lines (common in budgets).
            tables = camelot.read_pdf(record.location, pages='1-20', flavor='lattice')
            
            extracted_data = []
            for table in tables:
                # Convert table to list of lists (JSON serializable)
                # accuracy attribute tells us how confident Camelot is
                if table.accuracy > 80:
                    df = table.df
                    # Clean up: Replace NaNs/None with empty strings
                    clean_data = df.fillna("").values.tolist()
                    extracted_data.append(clean_data)

            # Store the result (list of tables, where each table is a list of rows)
            record.tables = extracted_data
            print(f"Found {len(extracted_data)} high-confidence tables.")
            
            session.commit()

        except Exception as e:
            print(f"Error extracting tables from {record.filename}: {e}")
            # Mark as empty so we don't retry forever
            record.tables = []
            try:
                session.commit()
            except:
                session.rollback()

    session.close()
    print("Table extraction complete.")

if __name__ == "__main__":
    extract_tables()
