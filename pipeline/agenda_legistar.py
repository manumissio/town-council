import logging
from datetime import date
from typing import List, Dict, Any, Optional

import html as _html
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


logger = logging.getLogger("agenda-legistar")

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html_to_text(value: str) -> str:
    """
    Convert simple HTML fragments (common in Legistar titles) into plain text.

    Why this exists:
    - Legistar fields sometimes include tags like <em> or <br>.
    - Meilisearch also injects its own <em class=...> tags for highlights.
      Storing raw HTML in DB/index makes the UI look broken and increases risk.
    """
    if not value:
        return ""

    # Convert <br> to space/newline boundaries before stripping tags.
    v = re.sub(r"(?i)<br\s*/?>", " ", value)
    v = _TAG_RE.sub(" ", v)
    v = _html.unescape(v)
    # Collapse any double spaces created by tag stripping.
    v = re.sub(r"\s+", " ", v).strip()
    return v

def build_legistar_session() -> requests.Session:
    """
    Build a requests session with small retry budget for transient 5xx errors.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods={"GET"},
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _safe_title(item: Dict[str, Any]) -> str:
    # Legistar payload fields vary by city; use first useful title-like value.
    raw = (
        item.get("EventItemTitle")
        or item.get("EventItemMatterName")
        or item.get("EventItemMatterFile")
        or ""
    ).strip()
    return strip_html_to_text(raw)


def fetch_legistar_agenda_items(
    legistar_client: Optional[str],
    event_date: Optional[date],
    timeout: float = 8.0,
    max_items: int = 50,
    http: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch normalized agenda items from Legistar for one city/date.
    """
    if not legistar_client or not event_date:
        return []

    session = http or build_legistar_session()
    date_str = event_date.isoformat()

    try:
        # Step 1: find Legistar event id for our meeting date.
        events_url = (
            f"https://webapi.legistar.com/v1/{legistar_client}/events"
            f"?$filter=EventDate eq datetime'{date_str}'"
        )
        events_res = session.get(events_url, timeout=(3.0, timeout))
        events_res.raise_for_status()
        events_payload = events_res.json() or []
        if not events_payload:
            return []

        event_id = events_payload[0].get("EventId")
        if not event_id:
            return []

        # Step 2: get item rows and normalize to our schema.
        items_url = f"https://webapi.legistar.com/v1/{legistar_client}/events/{event_id}/EventItems"
        items_res = session.get(items_url, timeout=(3.0, timeout))
        items_res.raise_for_status()
        raw_items = items_res.json() or []

        normalized = []
        for raw in raw_items[:max_items]:
            title = _safe_title(raw)
            if not title:
                continue
            agenda_number = str(raw.get("EventItemAgendaNumber") or "").strip()
            matter_id = raw.get("EventItemMatterId")

            normalized.append({
                "order": len(normalized) + 1,
                "title": title,
                "description": f"Legistar item {agenda_number}" if agenda_number else "Legistar agenda item",
                "classification": "Agenda Item",
                "result": "",
                "page_number": None,
                "legistar_matter_id": matter_id,
            })

        return normalized
    except requests.RequestException as exc:
        logger.warning(f"Legistar cross-check failed for client={legistar_client} date={date_str}: {exc}")
        return []
