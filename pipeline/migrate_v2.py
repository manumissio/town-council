import os
import sys
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pipeline.models import db_connect, Base, Place, Organization, Event

def migrate_db():
    """
    Migration Script: Updates the database schema to include the 'organization' table 
    and the 'organization_id' column in the 'event' table.
    
    Why: SQLAlchemy's metadata.create_all() only creates NEW tables; it doesn't 
    add columns to existing tables. We must do this manually.
    """
    print("Connecting to database for schema migration...")
    engine = db_connect()
    
    # 1. Create the new 'organization' table if it doesn't exist
    Base.metadata.create_all(engine)
    print("Ensured 'organization' table exists.")

    # 2. Add 'organization_id' column to 'event' and 'event_stage'
    # We use a try/except because if the column already exists, this will fail.
    with engine.connect() as conn:
        print("Checking for 'organization_id' column in 'event'...")
        try:
            conn.execute(text("ALTER TABLE event ADD COLUMN organization_id INTEGER REFERENCES organization(id)"))
            conn.commit()
            print("Added organization_id to 'event' table.")
        except Exception as e:
            print(f"Skipping 'event' column addition (it might already exist): {e}")

        print("Checking for 'organization_name' column in 'event_stage'...")
        try:
            conn.execute(text("ALTER TABLE event_stage ADD COLUMN organization_name VARCHAR"))
            conn.commit()
            print("Added organization_name to 'event_stage' table.")
        except Exception as e:
            print(f"Skipping 'event_stage' column addition (it might already exist): {e}")

if __name__ == "__main__":
    migrate_db()
