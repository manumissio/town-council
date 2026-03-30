# Profiling manifests

Keep pinned catalog manifests for `scripts/profile_pipeline.py --mode baseline` in this directory.

Format:
- one catalog ID per line
- blank lines are ignored
- `#` starts an inline comment

Example:
```text
12345
67890  # include a representative long agenda
```

Rules:
- use stable catalog sets when you want before/after comparisons
- if the workload changes materially, treat the run as diagnostic instead of baseline-valid
