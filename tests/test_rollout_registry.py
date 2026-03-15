from pathlib import Path

import pytest

from pipeline import rollout_registry as mod


def test_load_wave_city_slugs_reads_registry_membership():
    assert mod.load_wave_city_slugs("wave1") == [
        "fremont",
        "hayward",
        "san_mateo",
        "sunnyvale",
        "san_leandro",
        "mtn_view",
        "moraga",
        "belmont",
    ]
    assert mod.load_wave_city_slugs("wave2") == [
        "orinda",
        "brisbane",
        "danville",
        "los_gatos",
        "los_altos",
        "palo_alto",
        "san_bruno",
        "east_palo_alto",
        "santa_clara",
    ]


def test_validate_rollout_registry_rejects_invalid_wave(tmp_path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        "city_slug,wave,enabled,quality_gate,stable_noop_eligible,last_verified_run_id,last_verified_at,last_fresh_pass_run_id\n"
        "hayward,wave3,yes,pass,no,,2026-03-14,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid wave"):
        mod.load_rollout_registry(path)


def test_validate_rollout_registry_rejects_invalid_status_values(tmp_path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        "city_slug,wave,enabled,quality_gate,stable_noop_eligible,last_verified_run_id,last_verified_at,last_fresh_pass_run_id\n"
        "hayward,wave1,maybe,pass,no,,2026-03-14,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid enabled"):
        mod.load_rollout_registry(path)


def test_rollout_registry_script_contract_points_to_dedicated_metadata():
    assert Path("city_metadata/city_rollout_registry.csv").exists()


def test_validate_rollout_registry_requires_fresh_pass_reference_for_stable_noop(tmp_path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        "city_slug,wave,enabled,quality_gate,stable_noop_eligible,last_verified_run_id,last_verified_at,last_fresh_pass_run_id\n"
        "hayward,wave1,no,fail,yes,city_wave1_hayward_sanmateo_20260314_211707,2026-03-15,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="last_fresh_pass_run_id"):
        mod.load_rollout_registry(path)
