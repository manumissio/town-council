"""
One-command FAISS runtime verification for semantic search.

Usage:
  docker compose run --rm pipeline python check_faiss_runtime.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pipeline.config import SEMANTIC_INDEX_DIR


def main() -> int:
    print("=== faiss runtime check ===")
    try:
        import faiss  # type: ignore

        print(f"faiss_import=ok version={getattr(faiss, '__version__', 'unknown')}")
    except Exception as exc:
        print(f"faiss_import=failed error={exc.__class__.__name__}: {exc}")
        print(
            "remediation=faiss-cpu is unavailable in runtime. "
            "Semantic search will use numpy fallback unless SEMANTIC_REQUIRE_FAISS=true."
        )
        return 2

    meta_path = Path(SEMANTIC_INDEX_DIR) / "semantic_meta.json"
    if not meta_path.exists():
        print(f"semantic_meta=missing path={meta_path}")
        print("next_step=run docker compose run --rm pipeline python reindex_semantic.py")
        return 0

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"semantic_meta=invalid path={meta_path} error={exc.__class__.__name__}: {exc}")
        return 1

    engine = meta.get("engine", "unknown")
    print(f"semantic_meta=ok engine={engine} built_at={meta.get('built_at')}")
    if engine != "faiss":
        print(
            "note=faiss imports successfully but current artifacts are not FAISS. "
            "Rebuild with: docker compose run --rm pipeline python reindex_semantic.py"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
