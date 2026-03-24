import importlib.util
from pathlib import Path
import sys


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
