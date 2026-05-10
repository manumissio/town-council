from __future__ import annotations

from scripts.hydration_counts import rate_per_second


def emit_progress(enabled: bool, message: str) -> None:
    if enabled:
        print(message, flush=True)


def emit_stage_timing(city: str, stage: str, counts: dict[str, int], elapsed_seconds: float) -> None:
    selected_count = int(counts.get("selected", 0))
    completed_count = sum(int(counts.get(count_name, 0)) for count_name in ("updated", "cached", "complete"))
    print(
        f"[{city}] {stage}_timing elapsed_s={elapsed_seconds:.2f} "
        f"selected={selected_count} completed={completed_count} "
        f"rate_per_s={rate_per_second(completed_count, elapsed_seconds):.2f}",
        flush=True,
    )
