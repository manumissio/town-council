import datetime
import json

import scrapy

from council_crawler.utils import parse_date_string, url_to_md5
from .base import BaseCitySpider


class San_Mateo(BaseCitySpider):
    """
    Spider for San Mateo, CA using the city's official Laserfiche records portal.
    """

    name = "san_mateo"
    city_display_name = "San Mateo"
    ocd_division_id = "ocd-division/country:us/state:ca/place:san_mateo"
    portal_url = "https://www.cityofsanmateo.org/4588/Search-Legislative-Records"
    repo_name = "r-98a383e2"
    portal_base = "https://portal.laserfiche.com/Portal"
    page_size = 50
    bootstrap_days = 365
    max_future_days = 30
    session_retry_limit = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effective_last_meeting_date = self._sanitize_last_meeting_date(self.last_meeting_date)
        if self.last_meeting_date and self._effective_last_meeting_date is None:
            self.logger.warning(
                "Ignoring implausible San Mateo delta anchor %s and falling back to bounded bootstrap crawl",
                self.last_meeting_date,
            )

    def start_requests(self):
        # PrimeGov is host-wide robots-blocked for San Mateo, and Laserfiche's
        # query-builder endpoint has proven less reliable than the listing
        # endpoint itself, so we construct the known-good listing query directly.
        search_syn = self._build_search_syn()
        yield self._search_listing_request(
            search_syn=search_syn,
            search_uuid="",
            start_idx=1,
            get_new_listing=True,
        )

    def create_event_item(self, meeting_date, meeting_name, source_url, documents, meeting_type=None):
        event = super().create_event_item(
            meeting_date=meeting_date,
            meeting_name=meeting_name,
            source_url=source_url,
            documents=documents,
            meeting_type=meeting_type,
        )
        event["name"] = f"{self.city_display_name}, CA {meeting_name.strip()}"
        return event

    def parse_search_listing(self, response):
        if self._is_session_limited_response(response):
            yield from self._retry_session_limited_request(response)
            return

        payload = self._load_json(response)
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            self.logger.error("San Mateo Laserfiche listing returned invalid JSON payload")
            return

        results = data.get("results") or []
        hit_count = int(data.get("hitCount") or 0)
        search_syn = data.get("command") or response.meta["search_syn"]
        search_uuid = data.get("searchUUID") or response.meta.get("search_uuid", "")
        start_idx = int(response.meta["start_idx"])
        emitted_count = 0
        skipped_missing_count = 0
        skipped_old_count = 0
        page_has_new_results = False

        for row in results:
            event = self._event_from_result(row)
            if event is None:
                skipped_missing_count += 1
                continue

            if self.should_skip_meeting(event["record_date"]):
                skipped_old_count += 1
                continue

            page_has_new_results = True
            emitted_count += 1
            yield event

        self.logger.info(
            "San Mateo Laserfiche page start=%s accepted=%s skipped_missing=%s skipped_old=%s",
            start_idx,
            emitted_count,
            skipped_missing_count,
            skipped_old_count,
        )

        next_start = start_idx + self.page_size
        if results and next_start <= hit_count and page_has_new_results:
            yield self._search_listing_request(
                search_syn=search_syn,
                search_uuid=search_uuid,
                start_idx=next_start,
                get_new_listing=False,
            )

    def _search_listing_request(self, search_syn, search_uuid, start_idx, get_new_listing):
        return scrapy.Request(
            url=f"{self.portal_base}/SearchService.aspx/GetSearchListing",
            method="POST",
            headers=self._json_headers(),
            body=json.dumps(
                self._search_listing_payload(
                    search_syn=search_syn,
                    search_uuid=search_uuid,
                    start_idx=start_idx,
                    get_new_listing=get_new_listing,
                )
            ),
            callback=self.parse_search_listing,
            meta={
                "search_syn": search_syn,
                "search_uuid": search_uuid,
                "start_idx": start_idx,
                "search_retry_count": 0,
            },
        )

    def _search_listing_payload(self, search_syn, search_uuid, start_idx, get_new_listing):
        end_idx = start_idx + self.page_size - 1
        return {
            "repoName": self.repo_name,
            "searchSyn": search_syn,
            "searchUuid": search_uuid,
            "sortColumn": "LastModified",
            "startIdx": start_idx,
            "endIdx": end_idx,
            "getNewListing": get_new_listing,
            "sortOrder": 1,
            "displayInGridView": True,
        }

    def _event_from_result(self, row):
        entry_id = row.get("entryId")
        if not entry_id:
            return None

        metadata = self._metadata_map(row)
        agency = metadata.get("Agency", "").strip()
        if agency != "City Council":
            return None

        date_value = metadata.get("Date", "").strip()
        record_date = parse_date_string(date_value) if date_value else None
        if record_date is None:
            self.logger.info("Skipping San Mateo Laserfiche row without valid date: %s", row.get("name"))
            return None
        if self._is_implausible_future_date(record_date):
            self.logger.warning(
                "Skipping San Mateo Laserfiche row with implausible future date %s: %s",
                record_date,
                row.get("name"),
            )
            return None

        meeting_type = self._meeting_type_for_row(row, metadata)
        if not meeting_type:
            self.logger.info("Skipping San Mateo Laserfiche row without title: %s", entry_id)
            return None

        source_url = f"{self.portal_base}/DocView.aspx?id={entry_id}&repo={self.repo_name}"
        documents = [
            {
                "url": source_url,
                "url_hash": url_to_md5(source_url),
                "category": "agenda",
            }
        ]

        return self.create_event_item(
            meeting_date=record_date,
            meeting_name=meeting_type,
            source_url=source_url,
            documents=documents,
            meeting_type=meeting_type,
        )

    def _meeting_type_for_row(self, row, metadata):
        subject = metadata.get("Subject", "").strip()
        if subject:
            return subject
        name = (row.get("name") or "").strip()
        return name

    def _metadata_map(self, row):
        values = {}
        for entry in row.get("metadata") or []:
            name = entry.get("name")
            raw_values = entry.get("values") or []
            if not name or not raw_values:
                continue
            values[name] = str(raw_values[0])
        return values

    def _load_json(self, response):
        try:
            return json.loads((response.text or "").lstrip("\ufeff"))
        except json.JSONDecodeError as exc:
            snippet = (response.text or "")[:200].replace("\n", "\\n")
            self.logger.error(
                "Failed to parse San Mateo Laserfiche JSON from %s: %s. Body starts with: %r",
                response.url,
                exc,
                snippet,
            )
            return {}

    def _json_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Lf-Suppress-Login-Redirect": "1",
        }

    def _build_search_syn(self):
        clauses = ['{[]:[Agency]="City Council"}', "{[Agenda Reports]}"]
        if self._effective_last_meeting_date is None:
            # The first San Mateo bootstrap only needs enough recent corpus to
            # make onboarding decision-grade; later runs fall back to delta crawl.
            bootstrap_start = datetime.date.today() - datetime.timedelta(days=self.bootstrap_days)
            bootstrap_end = datetime.date.today()
            clauses.append(
                f'{{[]:[Date]>="{bootstrap_start.strftime("%-m/%-d/%Y")}", [Date]<="{bootstrap_end.strftime("%-m/%-d/%Y")}"}}'
            )
            self.logger.info("San Mateo bootstrap crawl window starts at %s", bootstrap_start)
        return f"({' & '.join(clauses)})"

    def _is_session_limited_response(self, response):
        body = (response.text or "").lower()
        return "sign in failed" in body and ("[9030]" in body or "session limit" in body)

    def _retry_session_limited_request(self, response):
        retry_count = int(response.meta.get("search_retry_count", 0))
        if retry_count >= self.session_retry_limit:
            self.logger.error(
                "San Mateo Laserfiche listing hit session limits after %s retries",
                retry_count,
            )
            return

        next_attempt = retry_count + 1
        self.logger.warning(
            "Retrying San Mateo Laserfiche listing after session-limit response (%s/%s)",
            next_attempt,
            self.session_retry_limit,
        )
        yield response.request.replace(
            dont_filter=True,
            meta={
                **response.meta,
                "search_retry_count": next_attempt,
            },
        )

    def should_skip_meeting(self, meeting_date):
        if not meeting_date:
            return True
        if self._is_implausible_future_date(meeting_date):
            return True
        return bool(self._effective_last_meeting_date and meeting_date <= self._effective_last_meeting_date)

    def _sanitize_last_meeting_date(self, meeting_date):
        if not meeting_date:
            return None
        if self._is_implausible_future_date(meeting_date):
            return None
        return meeting_date

    def _is_implausible_future_date(self, meeting_date):
        return meeting_date > (datetime.date.today() + datetime.timedelta(days=self.max_future_days))
