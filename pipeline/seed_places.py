import csv
import logging
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from pipeline.cli_logging import configure_cli_logging
from pipeline.models import Place, db_connect

LOGGER_NAME = "seed-places"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
CITY_METADATA_PATH = Path(__file__).resolve().parents[1] / "city_metadata" / "list_of_cities.csv"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup at the entrypoint so imports stay side-effect free."""
    configure_cli_logging(LOGGER_FORMAT)


def _derive_legistar_client(seed_url: str, hosting_services: str) -> str | None:
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


def _required_city_value(city_row: dict[str, str | None], column_name: str) -> str:
    city_value = city_row.get(column_name)
    if not city_value:
        raise ValueError(f"City metadata is missing {column_name}")
    return city_value


def _seed_city(session: Session, city_row: dict[str, str | None]) -> None:
    city_name = _required_city_value(city_row, "city")
    ocd_division_id = _required_city_value(city_row, "ocd_division_id")
    seed_url = _required_city_value(city_row, "city_council_url")
    hosting_service = _required_city_value(city_row, "hosting_services")
    display_name = _required_city_value(city_row, "display_name")
    legistar_client = _derive_legistar_client(seed_url, hosting_service)
    existing_place = (
        session.query(Place)
        .filter(Place.ocd_division_id == ocd_division_id)
        .first()
    )

    if existing_place:
        existing_place.seed_url = seed_url
        existing_place.hosting_service = hosting_service
        existing_place.legistar_client = legistar_client
        logger.info("Updated place: %s", display_name)
        return

    session.add(
        Place(
            name=city_name,
            type_="city",
            state=_required_city_value(city_row, "state"),
            country=_required_city_value(city_row, "country"),
            display_name=display_name,
            ocd_division_id=ocd_division_id,
            seed_url=seed_url,
            hosting_service=hosting_service,
            legistar_client=legistar_client,
            crawler=True,
            crawler_name=city_name,
            crawler_type="scrapy",
        )
    )
    logger.info("Added place: %s", display_name)


def _seed_city_metadata(session: Session, csv_path: Path) -> None:
    logger.info("Seeding places from %s...", csv_path)
    with csv_path.open(mode="r", encoding="utf-8") as city_metadata_file:
        for city_row in csv.DictReader(city_metadata_file):
            _seed_city(session, city_row)


def seed_places() -> None:
    """Seed cities after the canonical migration entrypoint has created the schema."""
    engine = db_connect()
    session = sessionmaker(bind=engine)()
    try:
        _seed_city_metadata(session, CITY_METADATA_PATH)
        session.commit()
        logger.info("Seeding complete.")
    except (SQLAlchemyError, OSError, ValueError) as error:
        logger.error("Error during seeding: %s", error, exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    _configure_cli_logging()
    seed_places()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
