from pathlib import Path

import pytest

from pipeline import rollout_registry as mod


REGISTRY_HEADER = (
    "city_slug,wave,enabled,quality_gate,stable_noop_eligible,"
    "last_verified_run_id,last_verified_at,last_fresh_pass_run_id,"
    "roster_source,roster_body_name,roster_source_verified_at\n"
)


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
        REGISTRY_HEADER
        + "hayward,wave3,yes,pass,no,,2026-03-14,,legistar_office_records,City Council,2026-07-31\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid wave"):
        mod.load_rollout_registry(path)


def test_validate_rollout_registry_rejects_invalid_status_values(tmp_path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        REGISTRY_HEADER
        + "hayward,wave1,maybe,pass,no,,2026-03-14,,legistar_office_records,City Council,2026-07-31\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid enabled"):
        mod.load_rollout_registry(path)


def test_rollout_registry_script_contract_points_to_dedicated_metadata():
    assert Path("city_metadata/city_rollout_registry.csv").exists()


def test_validate_rollout_registry_requires_fresh_pass_reference_for_stable_noop(tmp_path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        REGISTRY_HEADER
        + "hayward,wave1,no,fail,yes,city_wave1_hayward_sanmateo_20260314_211707,2026-03-15,,legistar_office_records,City Council,2026-07-31\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="last_fresh_pass_run_id"):
        mod.load_rollout_registry(path)


def test_registry_authorizes_only_explicit_verified_roster_sources():
    registry_by_city = {
        entry.city_slug: entry for entry in mod.load_rollout_registry()
    }

    for city_slug in ("cupertino", "hayward", "sunnyvale", "san_leandro"):
        entry = registry_by_city[city_slug]
        assert entry.roster_source == "legistar_office_records"
        assert entry.roster_body_name == "City Council"
        assert entry.roster_source_verified_at == "2026-07-31"
        assert entry.roster_authorized is True

    for city_slug in ("berkeley", "san_mateo"):
        entry = registry_by_city[city_slug]
        assert entry.enabled == "yes"
        assert entry.roster_source == ""
        assert entry.roster_body_name == ""
        assert entry.roster_source_verified_at == ""
        assert entry.roster_authorized is False


@pytest.mark.parametrize(
    ("roster_source", "roster_body_name", "verified_at"),
    [
        ("legistar_office_records", "", "2026-07-31"),
        ("legistar_office_records", "City Council", ""),
        ("", "City Council", "2026-07-31"),
    ],
)
def test_registry_rejects_partial_roster_authorization(
    tmp_path: Path,
    roster_source: str,
    roster_body_name: str,
    verified_at: str,
):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        REGISTRY_HEADER
        + (
            "hayward,wave1,yes,pass,no,,2026-03-14,,"
            f"{roster_source},{roster_body_name},{verified_at}\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="roster authorization"):
        mod.load_rollout_registry(path)


def test_registry_rejects_unknown_roster_source(tmp_path: Path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        REGISTRY_HEADER
        + "hayward,wave1,yes,pass,no,,2026-03-14,,scraped_minutes,City Council,2026-07-31\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid roster_source"):
        mod.load_rollout_registry(path)


def test_registry_requires_explicit_roster_authorization_columns(
    tmp_path: Path,
):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        (
            "city_slug,wave,enabled,quality_gate,stable_noop_eligible,"
            "last_verified_run_id,last_verified_at,last_fresh_pass_run_id\n"
            "hayward,wave1,yes,pass,no,,2026-03-14,\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing roster columns"):
        mod.load_rollout_registry(path)


def test_registry_rejects_invalid_roster_verification_date(tmp_path: Path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        REGISTRY_HEADER
        + "hayward,wave1,yes,pass,no,,2026-03-14,,legistar_office_records,City Council,07/31/2026\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="roster_source_verified_at"):
        mod.load_rollout_registry(path)


def test_registry_source_change_is_explicit_current_authorization(tmp_path: Path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        REGISTRY_HEADER
        + "hayward,wave1,yes,pass,no,,2026-03-14,,legistar_office_records,City Council,2026-07-31\n",
        encoding="utf-8",
    )
    approved_entry = mod.load_rollout_entry("hayward", path)

    path.write_text(
        REGISTRY_HEADER
        + "hayward,wave1,yes,pass,no,,2026-03-14,,,,\n",
        encoding="utf-8",
    )
    revoked_entry = mod.load_rollout_entry("hayward", path)

    assert approved_entry.roster_authorized is True
    assert revoked_entry.roster_authorized is False
    assert approved_entry.enabled == revoked_entry.enabled == "yes"


def test_disabled_city_is_not_roster_authorized(tmp_path: Path):
    path = tmp_path / "city_rollout_registry.csv"
    path.write_text(
        REGISTRY_HEADER
        + "hayward,wave1,no,pass,no,,2026-03-14,,legistar_office_records,City Council,2026-07-31\n",
        encoding="utf-8",
    )

    assert mod.load_rollout_entry("hayward", path).roster_authorized is False
