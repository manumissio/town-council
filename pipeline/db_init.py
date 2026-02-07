from pipeline.models import db_connect, create_tables

def init_db():
    """
    Explicitly creates the database tables.
    Run this script once when setting up the system.
    """
    print("Connecting to database...")
    engine = db_connect()
    
    print("Creating tables...")
    create_tables(engine)
    
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
