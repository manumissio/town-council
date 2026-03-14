import datetime
import json
import os
import sys

from scrapy.http import Request, TextResponse


sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "council_crawler"))

from council_crawler.spiders.ca_san_mateo import San_Mateo


def _json_response(url, payload, *, meta=None):
    request = Request(url=url, meta=meta or {})
    return TextResponse(
        url=url,
        body=json.dumps(payload),
        encoding="utf-8",
        request=request,
    )


def test_san_mateo_start_requests_build_bootstrap_query(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=None)
    spider = San_Mateo()

    requests = list(spider.start_requests())

    assert len(requests) == 1
    request = requests[0]
    payload = json.loads(request.body.decode("utf-8"))
    assert request.url.endswith("/CustomSearchService.aspx/GetSearchQuery")
    assert request.method == "POST"
    assert payload["repoName"] == "r-98a383e2"
    assert payload["searchFormID"] == "SearchforAgendaReports"
    assert payload["queryValues"]["SearchforAgendaReports_Input1"] == ["City Council"]
    assert "SearchforAgendaReports_Input0" in payload["queryValues"]
    assert "SearchforAgendaReports_Input0_end" in payload["queryValues"]


def test_san_mateo_search_query_builds_listing_request(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=None)
    spider = San_Mateo()

    response = _json_response(
        "https://portal.laserfiche.com/Portal/CustomSearchService.aspx/GetSearchQuery",
        {"data": '({[]:[Agency]="City Council"} & {[Agenda Reports]})'},
    )
    requests = list(spider.parse_search_query(response))

    assert len(requests) == 1
    request = requests[0]
    payload = json.loads(request.body.decode("utf-8"))
    assert request.url.endswith("/SearchService.aspx/GetSearchListing")
    assert request.method == "POST"
    assert payload["repoName"] == "r-98a383e2"
    assert payload["searchSyn"] == '({[]:[Agency]="City Council"} & {[Agenda Reports]})'
    assert payload["sortColumn"] == "LastModified"
    assert payload["sortOrder"] == 1
    assert payload["getNewListing"] is True


def test_san_mateo_listing_parser_emits_city_council_agenda_documents(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=None)
    spider = San_Mateo()

    payload = {
        "data": {
            "command": '({[]:[Agency]="City Council"} & {[Agenda Reports]})',
            "searchUUID": "uuid-1",
            "hitCount": 1,
            "results": [
                {
                    "entryId": 2040859,
                    "name": "2026-03-02 (7)",
                    "metadata": [
                        {"name": "Agency", "values": ["City Council"]},
                        {"name": "Date", "values": ["3/2/2026"]},
                        {"name": "Subject", "values": ["East 5th Avenue Apartments - Appeal"]},
                    ],
                }
            ],
        }
    }
    response = _json_response(
        "https://portal.laserfiche.com/Portal/SearchService.aspx/GetSearchListing",
        payload,
        meta={"search_syn": "ignored", "search_uuid": "", "start_idx": 1},
    )

    results = list(spider.parse_search_listing(response))

    assert len(results) == 1
    event = results[0]
    assert event["source"] == "san_mateo"
    assert event["ocd_division_id"] == "ocd-division/country:us/state:ca/place:san_mateo"
    assert event["name"] == "San Mateo, CA East 5th Avenue Apartments - Appeal"
    assert event["meeting_type"] == "East 5th Avenue Apartments - Appeal"
    assert event["record_date"] == datetime.date(2026, 3, 2)
    assert event["source_url"] == "https://portal.laserfiche.com/Portal/DocView.aspx?id=2040859&repo=r-98a383e2"
    assert event["documents"] == [
        {
            "url": "https://portal.laserfiche.com/Portal/DocView.aspx?id=2040859&repo=r-98a383e2",
            "url_hash": event["documents"][0]["url_hash"],
            "category": "agenda",
        }
    ]


def test_san_mateo_search_query_omits_bootstrap_start_when_delta_anchor_exists(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=datetime.date(2026, 3, 1))
    spider = San_Mateo()

    requests = list(spider.start_requests())

    assert len(requests) == 1
    payload = json.loads(requests[0].body.decode("utf-8"))
    assert payload["queryValues"] == {"SearchforAgendaReports_Input1": ["City Council"]}


def test_san_mateo_future_delta_anchor_falls_back_to_bootstrap_query(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=datetime.date(3023, 4, 3))
    spider = San_Mateo()

    requests = list(spider.start_requests())

    assert len(requests) == 1
    payload = json.loads(requests[0].body.decode("utf-8"))
    assert payload["queryValues"]["SearchforAgendaReports_Input1"] == ["City Council"]
    assert "SearchforAgendaReports_Input0" in payload["queryValues"]
    assert "SearchforAgendaReports_Input0_end" in payload["queryValues"]


def test_san_mateo_listing_parser_skips_invalid_rows_and_stops_after_old_page(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=datetime.date(2026, 3, 1))
    spider = San_Mateo()

    payload = {
        "data": {
            "command": "query",
            "searchUUID": "uuid-2",
            "hitCount": 100,
            "results": [
                {
                    "entryId": 2040858,
                    "name": "2026-03-02 (6)",
                    "metadata": [
                        {"name": "Agency", "values": ["Planning Commission"]},
                        {"name": "Date", "values": ["3/2/2026"]},
                    ],
                },
                {
                    "entryId": 2040857,
                    "name": "2026-03-01 (4)",
                    "metadata": [
                        {"name": "Agency", "values": ["City Council"]},
                        {"name": "Date", "values": ["3/1/2026"]},
                    ],
                },
                {
                    "entryId": 2040856,
                    "name": "Undated item",
                    "metadata": [
                        {"name": "Agency", "values": ["City Council"]},
                    ],
                },
            ],
        }
    }
    response = _json_response(
        "https://portal.laserfiche.com/Portal/SearchService.aspx/GetSearchListing",
        payload,
        meta={"search_syn": "query", "search_uuid": "uuid-2", "start_idx": 1},
    )

    results = list(spider.parse_search_listing(response))

    assert results == []


def test_san_mateo_listing_parser_paginates_when_new_results_exist(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=datetime.date(2026, 2, 1))
    spider = San_Mateo()

    payload = {
        "data": {
            "command": "query",
            "searchUUID": "uuid-3",
            "hitCount": 120,
            "results": [
                {
                    "entryId": 2040859,
                    "name": "2026-03-02 (7)",
                    "metadata": [
                        {"name": "Agency", "values": ["City Council"]},
                        {"name": "Date", "values": ["3/2/2026"]},
                    ],
                }
            ],
        }
    }
    response = _json_response(
        "https://portal.laserfiche.com/Portal/SearchService.aspx/GetSearchListing",
        payload,
        meta={"search_syn": "query", "search_uuid": "", "start_idx": 1},
    )

    results = list(spider.parse_search_listing(response))

    assert len(results) == 2
    event, next_request = results
    assert event["record_date"] == datetime.date(2026, 3, 2)
    assert next_request.url.endswith("/SearchService.aspx/GetSearchListing")
    payload = json.loads(next_request.body.decode("utf-8"))
    assert payload["searchUuid"] == "uuid-3"
    assert payload["startIdx"] == 51
    assert payload["getNewListing"] is False


def test_san_mateo_listing_parser_skips_implausible_future_dates(mocker):
    mocker.patch.object(San_Mateo, "_get_last_meeting_date", return_value=None)
    spider = San_Mateo()

    payload = {
        "data": {
            "command": "query",
            "searchUUID": "uuid-4",
            "hitCount": 1,
            "results": [
                {
                    "entryId": 2016464,
                    "name": "Future dated item",
                    "metadata": [
                        {"name": "Agency", "values": ["City Council"]},
                        {"name": "Date", "values": ["4/3/3023"]},
                        {"name": "Subject", "values": ["Underground Flow Equalization System Temporary Construction Access – Amendment"]},
                    ],
                }
            ],
        }
    }
    response = _json_response(
        "https://portal.laserfiche.com/Portal/SearchService.aspx/GetSearchListing",
        payload,
        meta={"search_syn": "query", "search_uuid": "uuid-4", "start_idx": 1},
    )

    results = list(spider.parse_search_listing(response))

    assert results == []
