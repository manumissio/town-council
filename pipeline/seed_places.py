import csv
import os
from typing import Optional
from urllib.parse import urlparse
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Place, db_connect, create_tables

def _derive_legistar_client(seed_url: str, hosting_services: str) -> Optional[str]:
    """
    Derive the Legistar "client" slug used by the Legistar Web API.

    Example:
      "https://cupertino.legistar.com/Calendar.aspx" -> "cupertino"

    Why this exists:
    - Our agenda resolver can cross-check agenda items via Legistar's Web API.
    - That code needs `Place.legistar_client`.
    - We seed it in a generic way by parsing the subdomain for Legistar-hosted cities.
    """
    if not seed_url or not hosting_services:
        return None

    if "legistar" not in hosting_services.lower():
        return None

    try:
        host = (urlparse(seed_url).hostname or "").lower()
    except ValueError:
        return None

    if not host.endswith(".legistar.com"):
        return None

    subdomain = host.split(".")[0].strip()
    return subdomain or None

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
            # For Legistar-hosted cities, this unlocks a more reliable agenda resolver path.
            legistar_client = _derive_legistar_client(
                seed_url=row.get("city_council_url") or "",
                hosting_services=row.get("hosting_services") or "",
            )

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
                    legistar_client=legistar_client,
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
                existing.legistar_client = legistar_client
                print(f"Updated place: {row['display_name']}")

    try:
        session.commit()
        print("Seeding complete.")
    except (SQLAlchemyError, OSError, ValueError) as e:
        # Seeding errors: What can fail when loading city data?
        # - SQLAlchemyError: Database error (duplicate city, invalid foreign key)
        # - OSError: CSV file not found or unreadable
        # - ValueError: Malformed CSV (missing columns, invalid data)
        # Why rollback? Partial seeding creates inconsistent state
        print(f"Error during seeding: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    seed_places()
