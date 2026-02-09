import json
import os
import sys

from scrapy.http import TextResponse, Request

# Make sure tests can import both the repo root and the council_crawler package.
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "council_crawler"))

from templates.legistar_api import LegistarApi


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
    assert results[0]["documents"] == []

