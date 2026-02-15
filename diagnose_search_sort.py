"""
Compatibility wrapper for running the sort-diagnosis script from repo root.

In Docker, the `pipeline` service uses `working_dir: /app/pipeline`, so the canonical
script path lives at `pipeline/diagnose_search_sort.py`.
"""

from pipeline.diagnose_search_sort import main


if __name__ == "__main__":
    raise SystemExit(main())
