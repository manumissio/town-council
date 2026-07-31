from __future__ import annotations

import csv
from datetime import date
import re
from dataclasses import dataclass
from pathlib import Path


ROLLOUT_REGISTRY_PATH = Path("city_metadata/city_rollout_registry.csv")
CITY_METADATA_PATH = Path("city_metadata/list_of_cities.csv")
VALID_WAVES = {"", "wave1", "wave2"}
VALID_ENABLED = {"yes", "no"}
VALID_QUALITY_GATES = {"pass", "fail", "pending", "insufficient_data"}
VALID_STABLE_NOOP_ELIGIBLE = {"yes", "no"}
LEGISTAR_OFFICE_RECORDS_SOURCE = "legistar_office_records"
VALID_ROSTER_SOURCES = {"", LEGISTAR_OFFICE_RECORDS_SOURCE}
ROSTER_AUTHORIZATION_COLUMNS = {
    "roster_source",
    "roster_body_name",
    "roster_source_verified_at",
}
CITY_SLUG_RE = re.compile(r"^[a-z0-9_]+$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CITY_METADATA_ALIASES = {
    # Wave/onboarding script slugs must stay aligned with existing spider names.
    "mtn_view": "mountain_view",
}


@dataclass(frozen=True)
class RolloutEntry:
    city_slug: str
    wave: str
    enabled: str
    quality_gate: str
    stable_noop_eligible: str
    last_verified_run_id: str
    last_verified_at: str
    last_fresh_pass_run_id: str
    roster_source: str
    roster_body_name: str
    roster_source_verified_at: str

    @property
    def roster_authorized(self) -> bool:
        return (
            self.enabled == "yes"
            and self.roster_source == LEGISTAR_OFFICE_RECORDS_SOURCE
            and bool(self.roster_body_name)
            and _is_iso_date(self.roster_source_verified_at)
        )


def _normalize(value: str | None) -> str:
    return (value or "").strip()


def _is_iso_date(value: str) -> bool:
    if not ISO_DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def load_city_metadata_slugs(path: Path = CITY_METADATA_PATH) -> set[str]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        slugs = set()
        for row in reader:
            division = _normalize(row.get("ocd_division_id"))
            if "/place:" not in division:
                continue
            slugs.add(division.split("/place:", 1)[1])
    return slugs


def load_rollout_registry(path: Path = ROLLOUT_REGISTRY_PATH) -> list[RolloutEntry]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing_roster_columns = ROSTER_AUTHORIZATION_COLUMNS - set(reader.fieldnames or ())
        if missing_roster_columns:
            raise ValueError(f"rollout registry is missing roster columns: {sorted(missing_roster_columns)}")
        entries = [
            RolloutEntry(
                city_slug=_normalize(row.get("city_slug")),
                wave=_normalize(row.get("wave")),
                enabled=_normalize(row.get("enabled")),
                quality_gate=_normalize(row.get("quality_gate")),
                stable_noop_eligible=_normalize(row.get("stable_noop_eligible")),
                last_verified_run_id=_normalize(row.get("last_verified_run_id")),
                last_verified_at=_normalize(row.get("last_verified_at")),
                last_fresh_pass_run_id=_normalize(row.get("last_fresh_pass_run_id")),
                roster_source=_normalize(row.get("roster_source")),
                roster_body_name=_normalize(row.get("roster_body_name")),
                roster_source_verified_at=_normalize(row.get("roster_source_verified_at")),
            )
            for row in reader
        ]
    validate_rollout_registry(entries)
    return entries


def validate_rollout_registry(
    entries: list[RolloutEntry],
    *,
    city_slugs: set[str] | None = None,
) -> None:
    known_city_slugs = city_slugs if city_slugs is not None else load_city_metadata_slugs()
    seen: set[str] = set()

    for entry in entries:
        if not entry.city_slug:
            raise ValueError("rollout registry row is missing city_slug")
        if not CITY_SLUG_RE.match(entry.city_slug):
            raise ValueError(f"invalid city_slug in rollout registry: {entry.city_slug}")
        if entry.city_slug in seen:
            raise ValueError(f"duplicate city_slug in rollout registry: {entry.city_slug}")
        if entry.wave not in VALID_WAVES:
            raise ValueError(f"invalid wave for {entry.city_slug}: {entry.wave}")
        if entry.enabled not in VALID_ENABLED:
            raise ValueError(f"invalid enabled value for {entry.city_slug}: {entry.enabled}")
        if entry.quality_gate not in VALID_QUALITY_GATES:
            raise ValueError(f"invalid quality_gate for {entry.city_slug}: {entry.quality_gate}")
        if entry.stable_noop_eligible not in VALID_STABLE_NOOP_ELIGIBLE:
            raise ValueError(f"invalid stable_noop_eligible value for {entry.city_slug}: {entry.stable_noop_eligible}")
        if entry.stable_noop_eligible == "yes" and not entry.last_fresh_pass_run_id:
            raise ValueError(f"stable_noop_eligible city is missing last_fresh_pass_run_id: {entry.city_slug}")
        if entry.roster_source not in VALID_ROSTER_SOURCES:
            raise ValueError(f"invalid roster_source for {entry.city_slug}: {entry.roster_source}")
        roster_fields_present = (
            bool(entry.roster_source),
            bool(entry.roster_body_name),
            bool(entry.roster_source_verified_at),
        )
        if any(roster_fields_present) and not all(roster_fields_present):
            raise ValueError(f"incomplete roster authorization for {entry.city_slug}")
        if all(roster_fields_present) and not _is_iso_date(entry.roster_source_verified_at):
            raise ValueError(
                f"invalid roster_source_verified_at for {entry.city_slug}: {entry.roster_source_verified_at}"
            )
        metadata_city_slug = CITY_METADATA_ALIASES.get(entry.city_slug, entry.city_slug)
        if metadata_city_slug not in known_city_slugs:
            raise ValueError(f"rollout registry city_slug {entry.city_slug} is missing from {CITY_METADATA_PATH}")
        seen.add(entry.city_slug)


def load_wave_city_slugs(wave: str, path: Path = ROLLOUT_REGISTRY_PATH) -> list[str]:
    normalized_wave = _normalize(wave)
    if normalized_wave not in VALID_WAVES or normalized_wave == "":
        raise ValueError(f"unknown rollout wave: {wave}")

    return [entry.city_slug for entry in load_rollout_registry(path) if entry.wave == normalized_wave]


def load_rollout_entry(city_slug: str, path: Path = ROLLOUT_REGISTRY_PATH) -> RolloutEntry:
    for entry in load_rollout_registry(path):
        if entry.city_slug == city_slug:
            return entry
    raise ValueError(f"unknown city_slug in rollout registry: {city_slug}")
