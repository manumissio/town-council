import csv
import json
from pathlib import Path

from scripts.analyze_segmentation_quality_checkpoint import (
    _manual_review_summary,
    _per_catalog_report,
)
from scripts.build_segmentation_review_packet import build_review_rows


def test_build_review_rows_blinds_and_formats_items():
    control_rows = {
        933: {
            "catalog_id": 933,
            "task_result": {
                "items": [
                    {"title": "Control item 1", "description": "Desc 1", "page_number": 2},
                    {"title": "Control item 2", "description": "", "page_number": 3},
                ]
            },
        }
    }
    treatment_rows = {
        933: {
            "catalog_id": 933,
            "task_result": {
                "items": [
                    {"title": "Treatment item 1", "description": "Desc T", "page_number": 4},
                ]
            },
        }
    }
    blind_rows, key_rows = build_review_rows(
        control_rows=control_rows,
        treatment_rows=treatment_rows,
        source_map={933: "Source excerpt"},
        seed=42,
    )

    assert len(blind_rows) == 1
    assert len(key_rows) == 1
    blind = blind_rows[0]
    assert blind[0] == "S001"
    assert blind[1] == "933"
    assert blind[2] == "Source excerpt"
    assert "item 1" in blind[3].lower() or "item 1" in blind[4].lower()
    assert key_rows[0][2] in {"A", "B"}
    assert key_rows[0][3] in {"A", "B"}
    assert key_rows[0][2] != key_rows[0][3]


def test_manual_review_summary_flags_treatment_major_omissions(tmp_path: Path):
    blind_path = tmp_path / "blind.csv"
    key_path = tmp_path / "key.csv"
    with blind_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "sample_id",
                "catalog_id",
                "source_excerpt",
                "option_a_segmented_items",
                "option_b_segmented_items",
                "better_overall_option",
                "major_items_missing_in_a",
                "major_items_missing_in_b",
                "obvious_boilerplate_in_a",
                "obvious_boilerplate_in_b",
                "notes",
            ]
        )
        writer.writerow(["S001", "933", "src", "a", "b", "A", "", "Missed hearing item", "", "", ""])
    with key_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_id", "catalog_id", "option_a_arm", "option_b_arm"])
        writer.writerow(["S001", "933", "A", "B"])

    summary = _manual_review_summary(blind_path, key_path)
    assert summary["treatment_passes"] is False
    assert summary["treatment_failures"][0]["catalog_id"] == "933"
    assert summary["treatment_failures"][0]["type"] == "major_items_missing"


def test_per_catalog_report_applies_severity_and_count_guardrails():
    control_segments = {
        933: {
            "catalog_id": 933,
            "task_result": {
                "item_count": 12,
                "items": [{"title": f"Policy item {i}", "page_number": i + 1, "result": ""} for i in range(12)],
            },
        }
    }
    treatment_segments = {
        933: {
            "catalog_id": 933,
            "task_result": {
                "item_count": 2,
                "items": [
                    {"title": "Policy item 1", "page_number": 2, "result": ""},
                    {"title": "Policy item 2", "page_number": 3, "result": ""},
                ],
            },
        }
    }
    report = _per_catalog_report(control_segments, treatment_segments, {933: "[PAGE 2]\nPolicy item 1\n[PAGE 3]\nPolicy item 2\n"})
    assert len(report) == 1
    row = report[0]
    assert row["catalog_id"] == 933
    assert row["item_count_drop_pct"] > 50.0
    assert row["item_count_guardrail_pass"] is False


def test_quality_checkpoint_script_contract():
    text = Path("scripts/run_gemma4_host_metal_quality_checkpoint.py").read_text(encoding="utf-8")
    assert "experiments/gemma4_quality_checkpoint_cohort_v1.txt" in text
    assert "scripts/run_gemma4_host_metal_strict_swap.py" in text
    assert "scripts/build_segmentation_review_packet.py" in text
    assert "scripts/analyze_segmentation_quality_checkpoint.py" in text
    assert "quality_checkpoint_manifest.json" in text


def test_segmentation_review_packet_contract():
    text = Path("scripts/build_segmentation_review_packet.py").read_text(encoding="utf-8")
    assert "segmentation_review_blind_v1.csv" in text
    assert "segmentation_review_key_v1.csv" in text
    assert "major_items_missing_in_a" in text
    assert "major_items_missing_in_b" in text


def test_segmentation_quality_analysis_contract():
    text = Path("scripts/analyze_segmentation_quality_checkpoint.py").read_text(encoding="utf-8")
    assert "segmentation_quality_checkpoint_report.json" in text
    assert "item_count_guardrail_pass" in text
    assert "severity_guardrail_pass" in text
