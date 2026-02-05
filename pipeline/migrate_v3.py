import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import db_connect, Base

def migrate_v3():
    """
    Migration Script: Creates the 'person' and 'membership' tables in the live database.
    
    Why: This script ensures the Postgres database has the new tables needed 
    for Structured Membership & People Modeling.
    """
    print("Connecting to database for Improvement #2 migration...")
    engine = db_connect()
    
    # Create the new tables defined in models.py
    Base.metadata.create_all(engine)
    print("Successfully created 'person' and 'membership' tables.")

if __name__ == "__main__":
    migrate_v3()
