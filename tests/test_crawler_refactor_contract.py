import asyncio
import datetime
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest
import scrapy
from scrapy.http import HtmlResponse
from sqlalchemy.exc import SQLAlchemyError

CRAWLER_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "council_crawler"
sys.path.insert(0, str(CRAWLER_PACKAGE_ROOT))

from council_crawler import pipelines
from council_crawler.items import Event
from council_crawler.spiders import base as spider_base
from council_crawler.spiders.ca_belmont import Belmont
from council_crawler.spiders.ca_fremont import Fremont
from council_crawler.spiders.ca_moraga import Moraga
from council_crawler.utils import url_to_md5


def _response(url: str, body: str) -> HtmlResponse:
    return HtmlResponse(url=url, body=body, encoding="utf-8")


def _event_values(event: Event) -> dict[str, object]:
    event_values = dict(event)
    scraped_datetime = event_values.pop("scraped_datetime")
    assert isinstance(scraped_datetime, datetime.datetime)
    assert scraped_datetime.tzinfo is datetime.timezone.utc
    return event_values


def _disable_delta(
    monkeypatch: pytest.MonkeyPatch,
    spider_class: type[spider_base.BaseCitySpider],
) -> None:
    monkeypatch.setattr(spider_class, "_get_last_meeting_date", lambda _spider: None)


async def _collect_start_requests(
    spider: spider_base.TableArchiveSpider,
) -> list[scrapy.Request]:
    return [request async for request in spider.start()]


@pytest.mark.parametrize(
    ("spider_class", "expected_url"),
    [
        (
            Belmont,
            "http://www.belmont.gov/city-hall/city-government/city-meetings/-toggle-all",
        ),
        (Fremont, "https://fremont.gov/AgendaCenter/"),
        (Moraga, "http://www.moraga.ca.us/council/meetings/2017"),
    ],
)
def test_archive_spiders_define_scrapy_2_16_start_contract(
    monkeypatch: pytest.MonkeyPatch,
    spider_class: type[spider_base.TableArchiveSpider],
    expected_url: str,
) -> None:
    _disable_delta(monkeypatch, spider_class)
    spider = spider_class()

    assert spider_base.TableArchiveSpider.start is not scrapy.Spider.start
    [request] = asyncio.run(_collect_start_requests(spider))
    assert request.url == expected_url
    assert request.callback == spider.parse_archive


def test_belmont_archive_event_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_delta(monkeypatch, Belmont)
    spider = Belmont()
    response = _response(
        "http://www.belmont.gov/meetings",
        """
        <table><tbody><tr>
          <td><span itemprop="summary">Regular Meeting</span></td>
          <td class="event_datetime">February 10, 2026</td>
          <td class="event_agenda"><a href="/files/agenda.pdf">Agenda</a></td>
          <td class="event_minutes">
            <a href="https://records.example/minutes.pdf">Minutes</a>
          </td>
        </tr></tbody></table>
        """,
    )

    [event] = list(spider.parse_archive(response))
    agenda_url = "http://www.belmont.gov/files/agenda.pdf"
    minutes_url = "https://records.example/minutes.pdf"

    assert _event_values(event) == {
        "_type": "event",
        "ocd_division_id": "ocd-division/country:us/state:ca/place:belmont",
        "name": "Belmont, CA City Council Regular Meeting",
        "record_date": datetime.date(2026, 2, 10),
        "source": "belmont",
        "source_url": response.url,
        "meeting_type": "Regular Meeting",
        "documents": [
            {"url": agenda_url, "url_hash": url_to_md5(agenda_url), "category": "agenda"},
            {"url": minutes_url, "url_hash": url_to_md5(minutes_url), "category": "minutes"},
        ],
    }


def test_fremont_archive_event_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_delta(monkeypatch, Fremont)
    spider = Fremont()
    response = _response(
        "https://fremont.gov/AgendaCenter/",
        """
        <div class="listing">
          <h2>Planning Commission</h2>
          <table><tbody><tr>
            <td><h4><a>Details</a><a><strong><abbr>Feb</abbr>10, 2026</strong></a></h4></td>
            <td class="downloads"><div><div><div><div><ol>
              <li><a href="files/agenda.pdf">Agenda</a></li>
              <li><a href="https://cdn.example/packet.pdf">Packet</a></li>
            </ol></div></div></div></div></td>
            <td class="minutes"><a href="files/minutes.pdf">Minutes</a></td>
          </tr></tbody></table>
        </div>
        """,
    )

    [event] = list(spider.parse_archive(response))
    agenda_url = "https://fremont.gov/AgendaCenter/files/agenda.pdf"
    packet_url = "https://cdn.example/packet.pdf"
    minutes_url = "https://fremont.gov/AgendaCenter/files/minutes.pdf"

    assert _event_values(event) == {
        "_type": "event",
        "ocd_division_id": "ocd-division/country:us/state:ca/place:fremont",
        "name": "Fremont, CA City Council Planning Commission",
        "record_date": datetime.date(2026, 2, 10),
        "source": "fremont",
        "source_url": response.url,
        "meeting_type": "Planning Commission",
        "documents": [
            {"url": agenda_url, "url_hash": url_to_md5(agenda_url), "category": "agenda"},
            {"url": packet_url, "url_hash": url_to_md5(packet_url), "category": "agenda"},
            {"url": minutes_url, "url_hash": url_to_md5(minutes_url), "category": "minutes"},
        ],
    }


def test_moraga_archive_event_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_delta(monkeypatch, Moraga)
    spider = Moraga()
    response = _response(
        "http://www.moraga.ca.us/council/meetings/2017",
        """
        <table><tbody><tr>
          <td>February 10, 2026<a href="files/agenda packet.pdf">Regular Meeting</a></td>
          <td><a href="files/minutes.pdf">Minutes</a></td>
        </tr></tbody></table>
        """,
    )

    [event] = list(spider.parse_archive(response))
    agenda_url = "http://www.moraga.ca.us/council/meetings/files/agenda%20packet.pdf"
    minutes_url = "http://www.moraga.ca.us/council/meetings/files/minutes.pdf"

    assert _event_values(event) == {
        "_type": "event",
        "ocd_division_id": "ocd-division/country:us/state:ca/place:moraga",
        "name": "Moraga, CA City Council Regular Meeting",
        "record_date": datetime.date(2026, 2, 10),
        "source": "moraga",
        "source_url": response.url,
        "meeting_type": "Regular Meeting",
        "documents": [
            {"url": agenda_url, "url_hash": url_to_md5(agenda_url), "category": "agenda"},
            {"url": minutes_url, "url_hash": url_to_md5(minutes_url), "category": "minutes"},
        ],
    }


class _DatabaseProbeSpider(spider_base.BaseCitySpider):
    name = "database_probe"
    ocd_division_id = "ocd-division/test"


def test_base_spider_recovers_from_sqlalchemy_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_database_connection() -> None:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(spider_base, "db_connect", fail_database_connection)

    assert _DatabaseProbeSpider().last_meeting_date is None


def test_base_spider_propagates_unexpected_database_check_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_database_connection() -> None:
        raise ValueError("programming defect")

    monkeypatch.setattr(spider_base, "db_connect", fail_database_connection)

    with pytest.raises(ValueError, match="programming defect"):
        _DatabaseProbeSpider()


DatabaseFailure = SQLAlchemyError | ValueError


@dataclass
class _FailingSession:
    failure: DatabaseFailure
    rolled_back: bool = False
    closed: bool = False

    def add(self, _record: object) -> None:
        return None

    def commit(self) -> None:
        raise self.failure

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


@dataclass
class _SpiderProbe:
    logger: logging.Logger


def _event_with_document() -> Event:
    return Event(
        _type="event",
        ocd_division_id="ocd-division/test",
        name="Test, CA Regular Meeting",
        scraped_datetime=datetime.datetime.now(datetime.timezone.utc),
        record_date=datetime.date(2026, 2, 10),
        source="test",
        source_url="https://example.com/meeting",
        meeting_type="Regular Meeting",
        documents=[
            {
                "url": "https://example.com/agenda.pdf",
                "url_hash": url_to_md5("https://example.com/agenda.pdf"),
                "category": "agenda",
            }
        ],
    )


def _stage_document_pipeline(
    session_factory: Callable[[], _FailingSession],
) -> pipelines.StageDocumentLinkPipeline:
    pipeline = pipelines.StageDocumentLinkPipeline.__new__(
        pipelines.StageDocumentLinkPipeline
    )
    pipeline.Session = session_factory
    return pipeline


def test_document_pipeline_recovers_from_sqlalchemy_failure() -> None:
    session = _FailingSession(SQLAlchemyError("database unavailable"))
    pipeline = _stage_document_pipeline(lambda: session)
    event = _event_with_document()

    assert pipeline.process_item(
        event, _SpiderProbe(logging.getLogger("crawler-test"))
    ) is event
    assert session.rolled_back is True
    assert session.closed is True


def test_document_pipeline_propagates_unexpected_failure() -> None:
    session = _FailingSession(ValueError("programming defect"))
    pipeline = _stage_document_pipeline(lambda: session)

    with pytest.raises(ValueError, match="programming defect"):
        pipeline.process_item(
            _event_with_document(), _SpiderProbe(logging.getLogger("crawler-test"))
        )

    assert session.rolled_back is False
    assert session.closed is True
