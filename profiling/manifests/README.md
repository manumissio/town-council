# Profiling manifests

Keep pinned catalog manifests for `scripts/profile_pipeline.py --mode baseline` in this directory.

Format:
- one catalog ID per line
- blank lines are ignored
- `#` starts an inline comment
- optional sidecar: `<name>.json`
  - controlled preconditioning contract for the matching `.txt` manifest
  - used only by baseline profiling runs
  - should contain only workload-scoped resets for derived or rebuildable fields

Example:
```text
12345
67890  # include a representative long agenda
```

Rules:
- use stable catalog sets when you want before/after comparisons
- if the workload changes materially, treat the run as diagnostic instead of baseline-valid
- run `python scripts/build_profile_manifest.py --name <name>` first if you want to inspect candidate coverage before writing a manifest package
- use `python scripts/profile_pipeline.py --mode baseline --manifest profiling/manifests/<name>.txt --dry-run-prepare` to inspect sidecar resets without mutating the workload
