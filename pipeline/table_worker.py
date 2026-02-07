import os
import camelot
import json
from sqlalchemy.orm import sessionmaker
from pipeline.models import Catalog, db_connect, create_tables

def extract_tables():
    """
    Finds tables (like budgets or schedules) inside PDF documents.
    
    How it works (Camelot):
    1. It looks for PDFs that haven't been scanned for tables yet.
    2. It uses the 'Camelot' library to detect grid lines and table structures.
    3. It extracts the data into a clean, structured format (JSON) that we can search and display.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that have been downloaded but haven't been checked for tables.
    # We check if the 'tables' column is NULL.
    to_process = session.query(Catalog).filter(
        Catalog.location != 'placeholder',
        Catalog.tables == None
    ).all()

    print(f"Found {len(to_process)} documents for table extraction.")

    for record in to_process:
        # Skip if the file is missing.
        if not os.path.exists(record.location):
            print(f"Skipping missing file: {record.location}")
            record.tables = [] # Mark as processed (empty) so we don't try again.
            continue

        # Only PDFs can contain structured tables we can extract.
        if not record.filename.lower().endswith('.pdf'):
            record.tables = []
            continue

        print(f"Extracting tables from: {record.filename}")
        
        try:
            # use Camelot to read the PDF.
            # - pages='1-20': We only check the first 20 pages to keep it fast.
            # - flavor='lattice': This mode works best for tables that have visible grid lines (common in government docs).
            tables = camelot.read_pdf(record.location, pages='1-20', flavor='lattice')
            
            extracted_data = []
            for table in tables:
                # Only keep tables where Camelot is at least 80% sure it found a real table.
                if table.accuracy > 80:
                    df = table.df
                    # Clean up the data: Turn 'NaN' (Not a Number) into empty strings for cleaner display.
                    clean_data = df.fillna("").values.tolist()
                    extracted_data.append(clean_data)

            # Save the list of tables back to the database.
            record.tables = extracted_data
            print(f"Found {len(extracted_data)} high-confidence tables.")
            
            session.commit()

        except Exception as e:
            print(f"Error extracting tables from {record.filename}: {e}")
            # If it fails, mark as empty so we don't get stuck in a loop.
            record.tables = []
            try:
                session.commit()
            except:
                session.rollback()

    session.close()
    print("Table extraction complete.")

if __name__ == "__main__":
    extract_tables()
