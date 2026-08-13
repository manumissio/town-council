# Profiling manifests

Keep pinned catalog manifests for `scripts/profile_pipeline.py --mode baseline` in this directory.

Format:
- one catalog ID per line
- blank lines are ignored
- `#` starts an inline comment
- IDs must be positive and unique

Example:
```text
12345
67890  # include a representative long agenda
```

Rules:
- use stable catalog sets when you want before/after comparisons
- if the workload changes materially, treat the run as diagnostic instead of baseline-valid
- use only fresh pending work for new diagnostic captures
- the profiler rejects sibling `.json` files because synthetic replay packages are retired

Fresh-work trace:
- write the temporary catalog list under `experiments/results/` after the
  fresh crawl, promotion, and scoped downloader finish
- stop before `run_pipeline.py`
- require a nonempty `.txt` file and verify that its sibling `.json` does not
  exist
- run the profiler with `--diagnostic` and without `--skip-batch`
- treat the resulting artifacts as exploratory and non-comparable

Baseline lifecycle:
- `baseline_representative_v1` is immutable historical evidence. Its schema includes the retired document-derived people phase, so it is non-comparable with roster-gated runs.
- `baseline_representative_v2` is the active capture candidate. It uses a distinct catalog workload regenerated from a fresh local corpus and excludes the retired people phase.
- City Coverage Expansion and baseline promotion remain blocked until v2 produces a baseline-valid capture and a separate expected-baseline PR is reviewed and merged.
