import importlib.util
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline import db_session as db_session_module
from pipeline.models import Base, Catalog, Document, Event, Place


spec = importlib.util.spec_from_file_location(
    "repair_san_mateo_laserfiche_backlog",
    Path("scripts/repair_san_mateo_laserfiche_backlog.py"),
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_parse_docview_url_extracts_entry_id_and_repo():
    entry_id, repo = mod._parse_docview_url(
        "https://portal.laserfiche.com/Portal/DocView.aspx?id=2040856&repo=r-98a383e2"
    )

    assert entry_id == 2040856
    assert repo == "r-98a383e2"


def test_electronic_file_url_uses_docid_query_parameter():
    assert mod._electronic_file_url(2040856, "r-98a383e2") == (
        "https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid=2040856&repo=r-98a383e2"
    )


def test_target_path_reuses_existing_catalog_directory():
    path, filename = mod._target_path(
        "/app/data/us/ca/san_mateo/oldhash.html",
        "newhash",
    )

    assert path == "/app/data/us/ca/san_mateo/newhash.pdf"
    assert filename == "newhash.pdf"


class _FakeResponse:
    def __init__(self, *, content_type: str, chunks: list[bytes], status_code: int = 200):
        self.headers = {"Content-Type": content_type}
        self._chunks = chunks
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def iter_content(self, chunk_size: int = 0):
        yield from self._chunks


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.trust_env = True

    def get(self, url, stream=True, timeout=None):
        return self.response


def test_download_repaired_pdf_writes_validated_pdf_to_final_path(tmp_path, monkeypatch):
    target = mod.RepairTarget(
        catalog_id=12,
        old_url="https://portal.laserfiche.com/Portal/DocView.aspx?id=2040856&repo=r-98a383e2",
        location=str(tmp_path / "oldhash.html"),
    )
    monkeypatch.setattr(
        mod.requests,
        "Session",
        lambda: _FakeSession(_FakeResponse(content_type="application/pdf", chunks=[b"%PDF-1.7\nbody"])),
    )

    repair = mod._download_repaired_pdf(target)

    assert repair["path"] == str(tmp_path / f"{repair['new_hash']}.pdf")
    assert Path(repair["path"]).read_bytes() == b"%PDF-1.7\nbody"
    assert not list(tmp_path.glob("*.tmp.*"))


def test_download_repaired_pdf_rejects_html_and_leaves_no_artifact(tmp_path, monkeypatch):
    target = mod.RepairTarget(
        catalog_id=13,
        old_url="https://portal.laserfiche.com/Portal/DocView.aspx?id=2040857&repo=r-98a383e2",
        location=str(tmp_path / "oldhash.html"),
    )
    monkeypatch.setattr(
        mod.requests,
        "Session",
        lambda: _FakeSession(_FakeResponse(content_type="text/html", chunks=[b"<!doctype html>error"])),
    )

    try:
        mod._download_repaired_pdf(target)
    except ValueError as exc:
        assert "Unexpected content type" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected html response to fail")

    assert not any(tmp_path.iterdir())


def test_download_repaired_pdf_rejects_zero_byte_pdf(tmp_path, monkeypatch):
    target = mod.RepairTarget(
        catalog_id=14,
        old_url="https://portal.laserfiche.com/Portal/DocView.aspx?id=2040858&repo=r-98a383e2",
        location=str(tmp_path / "oldhash.html"),
    )
    monkeypatch.setattr(
        mod.requests,
        "Session",
        lambda: _FakeSession(_FakeResponse(content_type="application/pdf", chunks=[])),
    )

    try:
        mod._download_repaired_pdf(target)
    except ValueError as exc:
        assert "zero-byte PDF" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected zero-byte response to fail")

    assert not any(tmp_path.iterdir())


def test_select_targets_salvage_mode_only_returns_bad_repaired_rows(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'repair.sqlite'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session_module._SessionLocal = Session

    good_path = tmp_path / "good.pdf"
    good_path.write_bytes(b"%PDF-1.7\nvalid")
    zero_path = tmp_path / "zero.pdf"
    zero_path.write_bytes(b"")

    with db_session_module.db_session() as session:
        place = Place(id=1, name="San Mateo", state="CA", country="us", ocd_division_id="ocd/test")
        event = Event(id=1, place_id=1, source="san_mateo")
        good_catalog = Catalog(
            id=1,
            url="https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid=1&repo=r-98a383e2",
            url_hash="good",
            location=str(good_path),
        )
        bad_catalog = Catalog(
            id=2,
            url="https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid=2&repo=r-98a383e2",
            url_hash="bad",
            location=str(zero_path),
        )
        doc_good = Document(id=1, place_id=1, event_id=1, catalog_id=1, category="agenda", url=good_catalog.url)
        doc_bad = Document(id=2, place_id=1, event_id=1, catalog_id=2, category="agenda", url=bad_catalog.url)
        session.add_all([place, event, good_catalog, bad_catalog, doc_good, doc_bad])
        session.commit()

    try:
        targets = mod._select_targets(
            "san_mateo",
            limit=None,
            resume_after_id=None,
            salvage_bad_electronicfile=True,
        )
    finally:
        db_session_module._SessionLocal = None

    assert [target.catalog_id for target in targets] == [2]
    assert targets[0].mode == "salvage"
