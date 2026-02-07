import csv
import os
from sqlalchemy.orm import sessionmaker
from pipeline.models import Place, db_connect, create_tables

def seed_places():
    """
    Populates the database with the initial list of cities.
    
    Why this is needed:
    The application needs to know which cities (Places) exists before it can
    save meeting data for them. This script reads a simple CSV file of city
    information and ensures a record exists for each one in the 'place' table.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Locate the CSV file containing the city list.
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'city_metadata', 'list_of_cities.csv')
    
    if not os.path.exists(csv_path):
        print(f"Error: Metadata file not found at {csv_path}")
        return

    print(f"Seeding places from {csv_path}...")

    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Check if this city is already in our database.
            existing = session.query(Place).filter(
                Place.ocd_division_id == row['ocd_division_id']
            ).first()

            if not existing:
                # Create a new record for the city.
                place = Place(
                    name=row['city'],
                    type_='city',
                    state=row['state'],
                    country=row['country'],
                    display_name=row['display_name'],
                    ocd_division_id=row['ocd_division_id'],
                    seed_url=row['city_council_url'],
                    hosting_service=row['hosting_services'],
                    crawler=True,
                    crawler_name=row['city'],
                    crawler_type='scrapy'
                )
                session.add(place)
                print(f"Added place: {row['display_name']}")
            else:
                # If it exists, update the URL and hosting service details just in case they changed.
                existing.seed_url = row['city_council_url']
                existing.hosting_service = row['hosting_services']
                print(f"Updated place: {row['display_name']}")

    try:
        session.commit()
        print("Seeding complete.")
    except Exception as e:
        print(f"Error during seeding: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    seed_places()
