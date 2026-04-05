import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Event, EventStage, Place, db_connect, create_tables
from pipeline.utils import generate_ocd_id

LOGGER_NAME = "promote-stage"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the entrypoint so imports stay side-effect free."""
    logging.basicConfig(level=logging.INFO, format=LOGGER_FORMAT)


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
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    logger.info("Promoting EventStage records to Event...")

    # Get all the meetings currently sitting in the staging area.
    staged_events = session.query(EventStage).all()
    
    promoted_count = 0
    skipped_count = 0
    promoted_ids = []

    for staged in staged_events:
        # 1. Find the City (Place) this meeting belongs to.
        # We need to link the meeting to a valid Place ID in our database.
        place = session.query(Place).filter(
            Place.ocd_division_id == staged.ocd_division_id
        ).first()

        if not place:
            logger.warning(
                "Skipping EventStage id=%s reason=blocked_missing_place ocd_division_id=%s event=%s",
                staged.id,
                staged.ocd_division_id,
                staged.name,
            )
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
            promoted_ids.append(staged.id)
        else:
            logger.info(
                "Skipping EventStage id=%s reason=duplicate ocd_division_id=%s event=%s",
                staged.id,
                staged.ocd_division_id,
                staged.name,
            )
            skipped_count += 1

    try:
        # Save all the new events to the database.
        session.commit()
        logger.info(
            "Promotion complete. promoted=%s skipped_or_duplicates=%s",
            promoted_count,
            skipped_count,
        )
        
        # Clean up: Remove the processed records from the staging table.
        if promoted_ids:
            logger.info("Clearing %s promoted EventStage rows...", len(promoted_ids))
            session.query(EventStage).filter(EventStage.id.in_(promoted_ids)).delete(synchronize_session=False)
            session.commit()

    except SQLAlchemyError as e:
        # Database errors during event promotion: What can fail?
        # - IntegrityError: Duplicate event (same date/name/location)
        # - ForeignKeyError: Referenced place doesn't exist
        # - OperationalError: Database connection lost during bulk insert
        # Why rollback? If ANY promotion fails, undo ALL to keep staging/production in sync
        logger.error("Error during promotion: %s", e, exc_info=True)
        session.rollback()
    finally:
        session.close()


def main() -> int:
    _configure_cli_logging()
    promote_stage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
