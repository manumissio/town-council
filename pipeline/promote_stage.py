import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from pipeline.cli_logging import configure_cli_logging
from pipeline.config_processing import load_processing_config
from pipeline.models import Event, EventStage, Place, db_connect
from pipeline.run_pipeline_onboarding import onboarding_ocd_division_id, parse_onboarding_started_at
from pipeline.utils import generate_ocd_id

LOGGER_NAME = "promote-stage"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the entrypoint so imports stay side-effect free."""
    configure_cli_logging(LOGGER_FORMAT)


def _staged_events_for_current_scope(session: Session) -> list[EventStage]:
    processing_config = load_processing_config()
    staged_events = session.query(EventStage)
    if not processing_config.pipeline_onboarding_city:
        return staged_events.all()

    staged_events = staged_events.filter(
        EventStage.ocd_division_id
        == onboarding_ocd_division_id(processing_config.pipeline_onboarding_city)
    )
    onboarding_started_at = parse_onboarding_started_at(
        processing_config.pipeline_onboarding_started_at_utc,
        logger=logger,
    )
    if onboarding_started_at is None:
        raise ValueError(
            "PIPELINE_ONBOARDING_STARTED_AT_UTC must be a valid UTC timestamp "
            "when PIPELINE_ONBOARDING_CITY is set"
        )
    staged_events = staged_events.filter(
        EventStage.scraped_datetime >= onboarding_started_at
    )
    return staged_events.all()


def _promote_staged_events(session: Session) -> tuple[list[int], int, int]:
    promoted_count = 0
    skipped_count = 0
    promoted_ids: list[int] = []

    for staged_event in _staged_events_for_current_scope(session):
        place = (
            session.query(Place)
            .filter(Place.ocd_division_id == staged_event.ocd_division_id)
            .first()
        )
        if not place:
            logger.warning(
                "Skipping EventStage id=%s reason=blocked_missing_place ocd_division_id=%s event=%s",
                staged_event.id,
                staged_event.ocd_division_id,
                staged_event.name,
            )
            skipped_count += 1
            continue

        existing_event = (
            session.query(Event)
            .filter(
                Event.ocd_division_id == staged_event.ocd_division_id,
                Event.record_date == staged_event.record_date,
                Event.name == staged_event.name,
            )
            .first()
        )
        if existing_event:
            logger.info(
                "Skipping EventStage id=%s reason=duplicate ocd_division_id=%s event=%s",
                staged_event.id,
                staged_event.ocd_division_id,
                staged_event.name,
            )
            skipped_count += 1
            continue

        session.add(
            Event(
                ocd_id=generate_ocd_id("event"),
                ocd_division_id=staged_event.ocd_division_id,
                place_id=place.id,
                name=staged_event.name,
                scraped_datetime=staged_event.scraped_datetime,
                record_date=staged_event.record_date,
                source=staged_event.source,
                source_url=staged_event.source_url,
                meeting_type=staged_event.meeting_type,
            )
        )
        promoted_count += 1
        promoted_ids.append(staged_event.id)

    return promoted_ids, promoted_count, skipped_count


def _commit_promotion(
    session: Session,
    promoted_ids: list[int],
    promoted_count: int,
    skipped_count: int,
) -> None:
    if promoted_ids:
        logger.info("Clearing %s promoted EventStage rows...", len(promoted_ids))
        session.query(EventStage).filter(EventStage.id.in_(promoted_ids)).delete(
            synchronize_session=False
        )
    session.commit()
    logger.info(
        "Promotion complete. promoted=%s skipped_or_duplicates=%s",
        promoted_count,
        skipped_count,
    )


def promote_stage() -> None:
    """Promote staging rows only after the canonical migration has run."""
    engine = db_connect()
    session = sessionmaker(bind=engine)()
    try:
        logger.info("Promoting EventStage records to Event...")
        promotion = _promote_staged_events(session)
        _commit_promotion(session, *promotion)
    except SQLAlchemyError as error:
        logger.error("Error during promotion: %s", error, exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    _configure_cli_logging()
    promote_stage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
