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

Baseline lifecycle:
- `baseline_representative_v1` is immutable historical evidence. Its schema includes the retired document-derived people phase, so active preparation rejects it as non-comparable.
- `baseline_representative_v2` is the active capture candidate. It uses a distinct 30-catalog workload regenerated from a fresh local corpus, excludes the retired phase, and assigns eight catalogs to entity enrichment.
- City Coverage Expansion and baseline promotion remain blocked until v2 produces a baseline-valid capture and a separate expected-baseline PR is reviewed and merged.
