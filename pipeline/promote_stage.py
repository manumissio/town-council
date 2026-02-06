from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from models import Event, EventStage, Place, db_connect, create_tables
from utils import generate_ocd_id

def promote_stage():
    """
    Moves scraped meeting data from the 'staging' table to the 'production' table.
    
    Why this is needed:
    The crawler saves data to a temporary staging area first. This script checks
    that data for validity and duplicates before officially adding it to the main
    'Event' table that the application uses.
    """
    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Promoting EventStage records to Event...")

    # Get all the meetings currently sitting in the staging area.
    staged_events = session.query(EventStage).all()
    
    promoted_count = 0
    skipped_count = 0

    for staged in staged_events:
        # 1. Find the City (Place) this meeting belongs to.
        # We need to link the meeting to a valid Place ID in our database.
        place = session.query(Place).filter(
            Place.ocd_division_id == staged.ocd_division_id
        ).first()

        if not place:
            print(f"Warning: No place found for {staged.ocd_division_id}. Skipping event: {staged.name}")
            skipped_count += 1
            continue

        # 2. Check for Duplicates.
        # Don't add the meeting if we already have it (same city, same date, same name).
        existing = session.query(Event).filter(
            Event.ocd_division_id == staged.ocd_division_id,
            Event.record_date == staged.record_date,
            Event.name == staged.name
        ).first()

        if not existing:
            # 3. Create the Production Record.
            # Copy valid data from staging to the live Event table.
            event = Event(
                ocd_id=generate_ocd_id('event'),
                ocd_division_id=staged.ocd_division_id,
                place_id=place.id,
                name=staged.name,
                scraped_datetime=staged.scraped_datetime,
                record_date=staged.record_date,
                source=staged.source,
                source_url=staged.source_url,
                meeting_type=staged.meeting_type
            )
            session.add(event)
            promoted_count += 1
        else:
            skipped_count += 1

    try:
        # Save all the new events to the database.
        session.commit()
        print(f"Promotion complete. {promoted_count} events promoted, {skipped_count} skipped/duplicates.")
        
        # Clean up: Remove the processed records from the staging table.
        if promoted_count > 0:
            print("Clearing EventStage table...")
            session.query(EventStage).delete()
            session.commit()
            
    except Exception as e:
        print(f"Error during promotion: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    promote_stage()
