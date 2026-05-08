from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("semantic-index")


def _semantic_index_facade():
    from pipeline import semantic_index

    return semantic_index


def _artifact_paths(backend) -> dict[str, Path]:
    base = Path(_semantic_index_facade().SEMANTIC_INDEX_DIR)
    return {
        "dir": base,
        "faiss": base / "semantic_index.faiss",
        "npy": base / "semantic_index.npy",
        "ids": base / "semantic_ids.json",
        "meta": base / "semantic_meta.json",
    }


def _load_artifacts(backend) -> None:
    backend._guard_runtime()
    if backend._index is not None and backend._metadata:
        return
    paths = backend._artifact_paths()
    if not paths["ids"].exists() or not paths["meta"].exists():
        raise FileNotFoundError("Semantic artifacts are missing. Run `python reindex_semantic.py`.")
    with backend._lock:
        if backend._index is None:
            faiss_backend = _semantic_index_facade().faiss
            backend._metadata = json.loads(paths["ids"].read_text(encoding="utf-8"))
            backend._meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
            if faiss_backend is not None and paths["faiss"].exists():
                backend._index = faiss_backend.read_index(str(paths["faiss"]))
                backend._matrix = None
            elif paths["npy"].exists():
                backend._matrix = np.load(paths["npy"], allow_pickle=False)
                backend._index = backend._matrix
            else:
                raise FileNotFoundError("Semantic index vectors are missing. Run `python reindex_semantic.py`.")


def _write_artifacts(
    backend, vectors: np.ndarray, metadata_rows: list[dict[str, Any]], build_meta: dict[str, Any]
) -> None:
    paths = backend._artifact_paths()
    paths["dir"].mkdir(parents=True, exist_ok=True)

    temp_faiss = paths["faiss"].with_suffix(".faiss.tmp")
    temp_npy = paths["npy"].with_suffix(".npy.tmp")
    temp_ids = paths["ids"].with_suffix(".json.tmp")
    temp_meta = paths["meta"].with_suffix(".json.tmp")

    faiss_backend = _semantic_index_facade().faiss
    if faiss_backend is not None:
        index = faiss_backend.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss_backend.write_index(index, str(temp_faiss))
        build_meta["engine"] = "faiss"
    else:
        logger.warning("faiss-cpu is unavailable; using numpy semantic index fallback.")
        with open(temp_npy, "wb") as fh:
            np.save(fh, vectors)
        build_meta["engine"] = "numpy"

    temp_ids.write_text(json.dumps(metadata_rows, ensure_ascii=False), encoding="utf-8")
    temp_meta.write_text(json.dumps(build_meta, ensure_ascii=False), encoding="utf-8")

    if faiss_backend is not None:
        os.replace(temp_faiss, paths["faiss"])
        if paths["npy"].exists():
            os.remove(paths["npy"])
    else:
        os.replace(temp_npy, paths["npy"])
        if paths["faiss"].exists():
            os.remove(paths["faiss"])
    os.replace(temp_ids, paths["ids"])
    os.replace(temp_meta, paths["meta"])
