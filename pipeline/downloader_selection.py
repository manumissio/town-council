import logging
import os
from datetime import datetime, timezone

from pipeline.models import UrlStage

logger = logging.getLogger(__name__)

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _parse_onboarding_started_at(raw_value: str | None):
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, ISO_FMT).replace(tzinfo=timezone.utc).replace(tzinfo=None)
    except ValueError:
        logger.warning("downloader_onboarding_scope invalid_started_at=%r", value)
        return None


def _select_staged_url_ids(session) -> list[int]:
    query = session.query(UrlStage.id)
    onboarding_city = str(os.getenv("PIPELINE_ONBOARDING_CITY", "") or "").strip()
    if not onboarding_city:
        return [r.id for r in query.all()]

    # Onboarding validation should only pull staged URLs created by the current
    # city run, otherwise unrelated backlog can leak into the city verdict.
    onboarding_ocd_division_id = f"ocd-division/country:us/state:ca/place:{onboarding_city}"
    query = query.filter(UrlStage.ocd_division_id == onboarding_ocd_division_id)

    onboarding_started_at = _parse_onboarding_started_at(os.getenv("PIPELINE_ONBOARDING_STARTED_AT_UTC"))
    if onboarding_started_at is not None:
        query = query.filter(UrlStage.created_at >= onboarding_started_at)

    return [r.id for r in query.all()]
