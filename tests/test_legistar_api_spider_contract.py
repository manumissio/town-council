import datetime
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

from scrapy.http import TextResponse, Request

# Make sure tests can import both the repo root and the council_crawler package.
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "council_crawler"))

from templates.legistar_api import LegistarApi
from council_crawler.spiders.ca_sunnyvale import Sunnyvale


def test_legistar_api_spider_maps_event_fields_and_documents(mocker):
    """
    Contract test for the Legistar Web API spider template.

    This is intentionally not Cupertino-specific. Cupertino is one consumer of
    this template, but other cities can reuse it without rewriting core logic.
    """
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=None)
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")

    mock_data = [
        {
            "EventBodyName": "City Council",
            "EventDate": "2026-02-10T00:00:00",
            "EventAgendaFile": "https://cupertino.legistar.com/agenda.pdf",
            "EventMinutesFile": "https://cupertino.legistar.com/minutes.pdf",
            "EventInSiteURL": "https://cupertino.legistar.com/MeetingDetail.aspx?ID=123",
        }
    ]

    url = "https://webapi.legistar.com/v1/cupertino/events"
    response = TextResponse(
        url=url,
        body=json.dumps(mock_data),
        encoding="utf-8",
        request=Request(url=url),
    )

    results = list(spider.parse(response))
    assert len(results) == 1

    evt = results[0]
    assert evt["ocd_division_id"] == "ocd-division/country:us/state:ca/place:cupertino"
    assert evt["meeting_type"] == "City Council"
    assert evt["source_url"] == "https://cupertino.legistar.com/MeetingDetail.aspx?ID=123"
    assert evt["record_date"].year == 2026

    docs = evt["documents"]
    assert [d["category"] for d in docs] == ["agenda", "minutes"]
    assert all(d["url"].startswith("https://") for d in docs)
    assert all(len(d["url_hash"]) == 32 for d in docs)  # md5 hex


def test_sunnyvale_spider_uses_legistar_api_client(mocker):
    mocker.patch.object(Sunnyvale, "_get_last_meeting_date", return_value=None)
    spider = Sunnyvale()

    [request] = list(spider.start_requests())

    assert spider.name == "sunnyvale"
    assert spider.client_name == "sunnyvaleca"
    assert spider.ocd_division_id == "ocd-division/country:us/state:ca/place:sunnyvale"
    assert request.url.startswith("https://webapi.legistar.com/v1/sunnyvaleca/events?")


def test_sunnyvale_api_spider_preserves_body_event_names(mocker):
    mocker.patch.object(Sunnyvale, "_get_last_meeting_date", return_value=None)
    spider = Sunnyvale()

    response = TextResponse(
        url="https://webapi.legistar.com/v1/sunnyvaleca/events",
        body=json.dumps(
            [
                {
                    "EventBodyName": "Planning Commission",
                    "EventDate": "2026-02-10T00:00:00",
                    "EventAgendaFile": "https://sunnyvaleca.legistar.com/agenda.pdf",
                    "EventMinutesFile": "https://sunnyvaleca.legistar.com/minutes.pdf",
                    "EventInSiteURL": "https://sunnyvaleca.legistar.com/MeetingDetail.aspx?ID=123",
                }
            ]
        ),
        encoding="utf-8",
        request=Request(url="https://webapi.legistar.com/v1/sunnyvaleca/events"),
    )

    [event] = list(spider.parse(response))

    assert event["name"] == "Sunnyvale, CA Planning Commission"
    assert [doc["url"] for doc in event["documents"]] == [
        "https://sunnyvaleca.legistar.com/agenda.pdf",
        "https://sunnyvaleca.legistar.com/minutes.pdf",
    ]


def test_sunnyvale_api_spider_does_not_duplicate_city_council_name(mocker):
    mocker.patch.object(Sunnyvale, "_get_last_meeting_date", return_value=None)
    spider = Sunnyvale()
    response = TextResponse(
        url="https://webapi.legistar.com/v1/sunnyvaleca/events",
        body=json.dumps(
            [
                {
                    "EventBodyName": "City Council",
                    "EventDate": "2026-02-10T00:00:00",
                    "EventAgendaFile": "https://sunnyvaleca.legistar.com/agenda.pdf",
                    "EventMinutesFile": None,
                    "EventInSiteURL": "https://sunnyvaleca.legistar.com/MeetingDetail.aspx?ID=123",
                }
            ]
        ),
        encoding="utf-8",
        request=Request(url="https://webapi.legistar.com/v1/sunnyvaleca/events"),
    )

    [request] = list(spider.parse(response))
    detail_response = TextResponse(
        url=request.url,
        body="",
        encoding="utf-8",
        request=Request(url=request.url),
    )
    [event] = list(request.callback(detail_response, **request.cb_kwargs))

    assert event["name"] == "Sunnyvale, CA City Council"


def test_legistar_api_spider_emits_no_documents_when_urls_missing(mocker):
    """
    Some events exist in the calendar without PDFs attached yet.
    The spider should not emit document entries with empty/None URLs.
    """
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=None)
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")

    mock_data = [
        {
            "EventBodyName": "City Council",
            "EventDate": "2026-02-10T00:00:00",
            "EventAgendaFile": None,
            "EventMinutesFile": None,
            "EventInSiteURL": "https://cupertino.legistar.com/MeetingDetail.aspx?ID=456",
        }
    ]

    url = "https://webapi.legistar.com/v1/cupertino/events"
    response = TextResponse(
        url=url,
        body=json.dumps(mock_data),
        encoding="utf-8",
        request=Request(url=url),
    )

    results = list(spider.parse(response))
    assert len(results) == 1
    assert results[0].url == "https://cupertino.legistar.com/MeetingDetail.aspx?ID=456"


def test_legistar_api_spider_falls_back_to_meeting_detail_documents(mocker):
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=None)
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")

    mock_data = [
        {
            "EventBodyName": "City Council",
            "EventDate": "2026-02-10T00:00:00",
            "EventAgendaFile": None,
            "EventMinutesFile": None,
            "EventInSiteURL": "https://cupertino.legistar.com/MeetingDetail.aspx?ID=456",
        }
    ]

    response = TextResponse(
        url="https://webapi.legistar.com/v1/cupertino/events",
        body=json.dumps(mock_data),
        encoding="utf-8",
        request=Request(url="https://webapi.legistar.com/v1/cupertino/events"),
    )

    [request] = list(spider.parse(response))
    detail_html = """
    <html><body>
      <a href="View.ashx?M=A&amp;ID=123">Agenda</a>
      <a href="View.ashx?M=M&amp;ID=123">Minutes</a>
      <a href="View.ashx?M=AO&amp;ID=123">Packet</a>
    </body></html>
    """
    detail_response = TextResponse(
        url=request.url,
        body=detail_html,
        encoding="utf-8",
        request=Request(url=request.url),
    )

    results = list(request.callback(detail_response, **request.cb_kwargs))
    assert len(results) == 1
    docs = results[0]["documents"]
    assert [doc["category"] for doc in docs] == ["agenda", "minutes"]
    assert docs[0]["url"] == "https://cupertino.legistar.com/View.ashx?M=A&ID=123"
    assert docs[1]["url"] == "https://cupertino.legistar.com/View.ashx?M=M&ID=123"


def test_legistar_api_spider_fetches_detail_when_one_api_document_is_missing(mocker):
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=None)
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")
    response = TextResponse(
        url="https://webapi.legistar.com/v1/cupertino/events",
        body=json.dumps(
            [
                {
                    "EventBodyName": "City Council",
                    "EventDate": "2026-02-10T00:00:00",
                    "EventAgendaFile": "https://cupertino.legistar.com/api-agenda.pdf",
                    "EventMinutesFile": None,
                    "EventInSiteURL": "https://cupertino.legistar.com/MeetingDetail.aspx?ID=456",
                }
            ]
        ),
        encoding="utf-8",
        request=Request(url="https://webapi.legistar.com/v1/cupertino/events"),
    )

    [request] = list(spider.parse(response))
    detail_response = TextResponse(
        url=request.url,
        body="""
        <html><body>
          <a href="https://cupertino.legistar.com/api-agenda.pdf">Agenda</a>
          <a href="View.ashx?M=M&amp;ID=456">Minutes</a>
        </body></html>
        """,
        encoding="utf-8",
        request=Request(url=request.url),
    )

    [event] = list(request.callback(detail_response, **request.cb_kwargs))
    assert [doc["category"] for doc in event["documents"]] == ["agenda", "minutes"]
    assert [doc["url"] for doc in event["documents"]] == [
        "https://cupertino.legistar.com/api-agenda.pdf",
        "https://cupertino.legistar.com/View.ashx?M=M&ID=456",
    ]


def test_legistar_api_spider_keeps_api_documents_when_detail_fetch_fails(mocker):
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=None)
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")
    response = TextResponse(
        url="https://webapi.legistar.com/v1/cupertino/events",
        body=json.dumps(
            [
                {
                    "EventBodyName": "City Council",
                    "EventDate": "2026-02-10T00:00:00",
                    "EventAgendaFile": "https://cupertino.legistar.com/api-agenda.pdf",
                    "EventMinutesFile": None,
                    "EventInSiteURL": "https://cupertino.legistar.com/MeetingDetail.aspx?ID=456",
                }
            ]
        ),
        encoding="utf-8",
        request=Request(url="https://webapi.legistar.com/v1/cupertino/events"),
    )

    [request] = list(spider.parse(response))
    failure = type("DetailFailure", (), {"request": request, "value": RuntimeError("detail failed")})()

    [event] = list(request.errback(failure))

    assert [doc["category"] for doc in event["documents"]] == ["agenda"]
    assert event["documents"][0]["url"] == "https://cupertino.legistar.com/api-agenda.pdf"


def test_legistar_api_spider_prefers_api_documents_without_duplicate_fallback(mocker):
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=None)
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")

    response = TextResponse(
        url="https://cupertino.legistar.com/MeetingDetail.aspx?ID=789",
        body="""
        <html><body>
          <a href="https://cupertino.legistar.com/agenda.pdf">Agenda</a>
          <a href="https://cupertino.legistar.com/minutes.pdf">Minutes</a>
        </body></html>
        """,
        encoding="utf-8",
        request=Request(url="https://cupertino.legistar.com/MeetingDetail.aspx?ID=789"),
    )

    docs = spider._dedupe_documents(
        spider._build_documents(
            agenda_url="https://cupertino.legistar.com/agenda.pdf",
            minutes_url="https://cupertino.legistar.com/minutes.pdf",
        )
        + spider._extract_detail_page_documents(response)
    )

    assert [doc["url"] for doc in docs] == [
        "https://cupertino.legistar.com/agenda.pdf",
        "https://cupertino.legistar.com/minutes.pdf",
    ]


def test_legistar_api_spider_paginates_full_event_history(mocker):
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=None)
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")
    event_rows = [
        {
            "EventBodyName": "City Council",
            "EventDate": "2026-02-10T00:00:00",
            "EventAgendaFile": None,
            "EventMinutesFile": None,
            "EventInSiteURL": "",
        }
        for _ in range(spider.page_size)
    ]
    response = TextResponse(
        url=spider._build_events_url(skip=0),
        body=json.dumps(event_rows),
        encoding="utf-8",
        request=Request(url=spider._build_events_url(skip=0)),
    )

    results = list(spider.parse(response, skip=0))

    next_request = results[-1]
    query = parse_qs(urlparse(next_request.url).query)
    assert isinstance(next_request, Request)
    assert query["$skip"] == ["1000"]
    assert next_request.cb_kwargs == {"skip": 1000}


def test_legistar_api_spider_stops_delta_pagination_after_old_meeting(mocker):
    mocker.patch.object(LegistarApi, "_get_last_meeting_date", return_value=datetime.date(2026, 2, 1))
    spider = LegistarApi(client="cupertino", city="cupertino", state="ca")
    spider.page_size = 2
    event_rows = [
        {
            "EventBodyName": "City Council",
            "EventDate": "2026-02-10T00:00:00",
            "EventAgendaFile": "https://cupertino.legistar.com/new-agenda.pdf",
            "EventMinutesFile": None,
            "EventInSiteURL": "",
        },
        {
            "EventBodyName": "City Council",
            "EventDate": "2026-01-10T00:00:00",
            "EventAgendaFile": "https://cupertino.legistar.com/old-agenda.pdf",
            "EventMinutesFile": None,
            "EventInSiteURL": "",
        },
    ]
    response = TextResponse(
        url=spider._build_events_url(skip=0),
        body=json.dumps(event_rows),
        encoding="utf-8",
        request=Request(url=spider._build_events_url(skip=0)),
    )

    results = list(spider.parse(response, skip=0))

    assert len(results) == 1
    assert not isinstance(results[0], Request)
    assert results[0]["source_url"] == ""
