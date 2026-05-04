import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias


ONBOARDING_STARTED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
CALIFORNIA_PLACE_DIVISION_PREFIX = "ocd-division/country:us/state:ca/place"

QueryLike: TypeAlias = object


@dataclass(frozen=True, slots=True)
class OnboardingScopeConfig:
    city: str
    started_at_utc: str


def parse_onboarding_started_at(raw_value: str, *, logger: logging.Logger) -> datetime | None:
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, ONBOARDING_STARTED_AT_FORMAT)
    except ValueError:
        logger.warning(
            "Invalid PIPELINE_ONBOARDING_STARTED_AT_UTC=%r; falling back to city-wide scope.",
            raw_value,
        )
        return None


def onboarding_ocd_division_id(city_slug: str) -> str:
    return f"{CALIFORNIA_PLACE_DIVISION_PREFIX}:{city_slug}"


def build_onboarding_touched_hashes_subquery(db: object, onboarding_started_at: datetime, ocd_division_id: str) -> object:
    from pipeline.models import UrlStage, UrlStageHist

    hist_hashes = (
        db.query(UrlStageHist.url_hash.label("url_hash"))
        .filter(
            UrlStageHist.ocd_division_id == ocd_division_id,
            UrlStageHist.created_at >= onboarding_started_at,
        )
    )
    live_hashes = (
        db.query(UrlStage.url_hash.label("url_hash"))
        .filter(
            UrlStage.ocd_division_id == ocd_division_id,
            UrlStage.created_at >= onboarding_started_at,
        )
    )
    return hist_hashes.union(live_hashes).subquery()


def scope_catalog_query_for_onboarding(
    db: object,
    query: QueryLike,
    *,
    config: OnboardingScopeConfig,
    logger: logging.Logger,
) -> tuple[QueryLike, int | None]:
    from pipeline.models import Catalog

    if not config.city:
        return query, None

    onboarding_started_at = parse_onboarding_started_at(config.started_at_utc, logger=logger)
    if onboarding_started_at is None:
        logger.warning(
            "onboarding_scope city=%s missing valid started_at; falling back to global selection",
            config.city,
        )
        return query.distinct(), None

    ocd_division_id = onboarding_ocd_division_id(config.city)
    touched_hashes = build_onboarding_touched_hashes_subquery(
        db,
        onboarding_started_at,
        ocd_division_id,
    )
    touched_hash_count = db.query(touched_hashes.c.url_hash).distinct().count()
    scoped = query.join(touched_hashes, touched_hashes.c.url_hash == Catalog.url_hash).distinct()
    logger.info(
        "onboarding_scope city=%s ocd_division_id=%s touched_hashes=%s source=url_stage_hist+url_stage",
        config.city,
        ocd_division_id,
        touched_hash_count,
    )
    return scoped, touched_hash_count
