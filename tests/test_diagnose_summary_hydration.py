import importlib.util
import sys
from pathlib import Path

from pipeline.summary_hydration_diagnostics import SummaryHydrationSnapshot


spec = importlib.util.spec_from_file_location(
    "diagnose_summary_hydration",
    Path("scripts/diagnose_summary_hydration.py"),
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_diagnose_summary_hydration_cli_labels_cumulative_vs_unresolved(mocker, capsys):
    snapshot = SummaryHydrationSnapshot(
        city="san_mateo",
        catalogs_with_content=100,
        catalogs_with_summary=25,
        missing_summary_total=75,
        agenda_missing_summary_total=70,
        agenda_missing_summary_with_items=10,
        agenda_missing_summary_without_items=60,
        non_agenda_missing_summary_total=5,
        non_agenda_summarizable=5,
        non_agenda_blocked_low_signal=0,
        agenda_segmentation_status_counts={"<null>": 55, "complete": 10, "empty": 5},
        sample_catalog_ids={
            "non_agenda_missing_summary": [1],
            "agenda_missing_summary_with_items": [2],
            "agenda_missing_summary_without_items": [3],
        },
        likely_root_cause="agenda_summaries_blocked_on_segmentation",
        cumulative_catalogs_with_content=100,
        cumulative_catalogs_with_summary=25,
        unresolved_missing_summary_total=75,
        agenda_missing_summary_total_unresolved=70,
        agenda_missing_summary_with_items_unresolved=10,
        agenda_missing_summary_without_items_unresolved=60,
        non_agenda_missing_summary_total_unresolved=5,
        agenda_unresolved_segmentation_status_counts={"<null>": 55, "complete": 10, "empty": 5},
    )
    mocker.patch.object(mod, "db_session")
    mocker.patch.object(mod, "build_summary_hydration_snapshot", return_value=snapshot)
    mocker.patch.object(sys, "argv", ["diagnose_summary_hydration.py", "--city", "san_mateo"])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Cumulative totals" in captured.out
    assert "Unresolved backlog totals" in captured.out
    assert "Backlog buckets (rows where summary is still null)" in captured.out
    assert "Agenda segmentation status counts (unresolved backlog only)" in captured.out
    assert "catalogs_with_summary is cumulative" in captured.out
