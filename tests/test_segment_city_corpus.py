import importlib.util
import subprocess
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location("segment_city_corpus", Path("scripts/segment_city_corpus.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_segment_catalog_subprocess_marks_timeout_failed(mocker):
    timeout_exc = subprocess.TimeoutExpired(cmd=["python"], timeout=5)
    run = mocker.patch.object(mod.subprocess, "run", side_effect=timeout_exc)
    mark_failed = mocker.patch.object(mod, "_mark_catalog_failed")

    outcome, duration_seconds, detail = mod._segment_catalog_subprocess(42, 5)

    run.assert_called_once()
    mark_failed.assert_called_once_with(42, "agenda_segmentation_timeout:5s")
    assert outcome == "timed_out"
    assert duration_seconds >= 0
    assert detail == "agenda_segmentation_timeout:5s"


def test_segment_catalog_subprocess_marks_failed_when_terminal_status_missing(mocker):
    run = mocker.patch.object(mod.subprocess, "run", return_value=mocker.Mock(stdout="", stderr=""))
    mocker.patch.object(mod, "_catalog_status", return_value=None)
    mark_failed = mocker.patch.object(mod, "_mark_catalog_failed")

    outcome, _duration_seconds, detail = mod._segment_catalog_subprocess(43, 5)

    run.assert_called_once()
    mark_failed.assert_called_once_with(43, "agenda_segmentation_missing_terminal_status")
    assert outcome == "failed"
    assert detail == "agenda_segmentation_missing_terminal_status"


def test_segment_city_corpus_continues_after_timeout(mocker, capsys):
    mocker.patch.object(mod, "_catalog_ids_for_city", return_value=[1, 2, 3])
    mocker.patch.object(mod, "_catalog_timeout_seconds", return_value=7)
    mocker.patch.object(
        mod,
        "_segment_catalog_subprocess",
        side_effect=[
            ("timed_out", 7.0, "agenda_segmentation_timeout:7s"),
            ("complete", 0.3, None),
            ("empty", 0.2, None),
        ],
    )

    mocker.patch.object(sys, "argv", ["segment_city_corpus.py", "--city", "sunnyvale"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "segmented city=sunnyvale catalog_count=3 complete=1 empty=1 failed=0 timed_out=1" in captured.out


def test_segment_city_corpus_reuses_shared_city_aliases():
    assert mod.source_aliases_for_city("san_mateo") == {"san_mateo", "san mateo"}
