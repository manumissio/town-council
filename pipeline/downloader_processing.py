import logging
import os

from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Catalog, Document, Event, UrlStage

logger = logging.getLogger(__name__)


def process_single_url(url_record_id, *, db_session_factory, media_cls):
    """
    Process one staged URL and link it to catalog/document rows.
    """
    try:
        with db_session_factory() as session:
            url_record = session.get(UrlStage, url_record_id)
            if not url_record:
                return False

            # Find the matching event so the downloaded file can be linked.
            event_record = (
                session.query(Event)
                .filter(
                    Event.ocd_division_id == url_record.ocd_division_id,
                    Event.record_date == url_record.event_date,
                    Event.name == url_record.event,
                )
                .first()
            )

            if not event_record:
                logger.info(
                    "downloader_skip_missing_event url_record_id=%s event=%s event_date=%s",
                    url_record_id,
                    url_record.event,
                    url_record.event_date,
                )
                return False

            catalog_entry = session.query(Catalog).filter(Catalog.url_hash == url_record.url_hash).first()

            if not catalog_entry:
                logger.info("downloader_fetch_start url_record_id=%s url=%s", url_record_id, url_record.url)
                downloader = media_cls(url_record)
                file_location = downloader.gather()

                if file_location:
                    try:
                        catalog_entry = Catalog(
                            url=url_record.url,
                            url_hash=url_record.url_hash,
                            location=file_location,
                            filename=os.path.basename(file_location),
                        )
                        session.add(catalog_entry)
                        session.flush()
                    except SQLAlchemyError:
                        # Another worker may have inserted the same hash first.
                        session.rollback()
                        logger.info(
                            "downloader_catalog_race_recovered url_record_id=%s url_hash=%s",
                            url_record_id,
                            url_record.url_hash,
                        )
                        catalog_entry = session.query(Catalog).filter(Catalog.url_hash == url_record.url_hash).first()
                else:
                    logger.error("downloader_fetch_failed url_record_id=%s url=%s", url_record_id, url_record.url)
                    return False

            existing_doc = (
                session.query(Document)
                .filter(
                    Document.event_id == event_record.id,
                    Document.catalog_id == catalog_entry.id,
                )
                .first()
            )

            if not existing_doc:
                document = Document(
                    place_id=event_record.place_id,
                    event_id=event_record.id,
                    catalog_id=catalog_entry.id,
                    url=url_record.url,
                    url_hash=url_record.url_hash,
                    category=url_record.category,
                )
                session.add(document)

            session.commit()
            return True
    except SQLAlchemyError as e:
        logger.error("downloader_process_failed url_record_id=%s error=%s", url_record_id, e)
        return False
