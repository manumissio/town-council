from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableConfig:
    table_accuracy_min: int
    table_scan_max_pages: int
    table_worker_cpu_fraction: float
    table_progress_log_interval: int


def load_table_config() -> TableConfig:
    return TableConfig(
        table_accuracy_min=70,
        table_scan_max_pages=5,
        table_worker_cpu_fraction=0.5,
        table_progress_log_interval=10,
    )
