import time

import numpy as np


def _old_topk(sims: np.ndarray, k: int) -> np.ndarray:
    return np.argsort(-sims)[:k]


def _new_topk(sims: np.ndarray, k: int) -> np.ndarray:
    if k >= sims.shape[0]:
        return np.argsort(-sims)
    idx = np.argpartition(-sims, k - 1)[:k]
    return idx[np.argsort(-sims[idx])]


def test_numpy_topk_new_matches_old_membership():
    rng = np.random.default_rng(42)
    sims = rng.random(10000, dtype=np.float32)
    k = 200
    old_idx = _old_topk(sims, k)
    new_idx = _new_topk(sims, k)
    assert set(old_idx.tolist()) == set(new_idx.tolist())


def test_numpy_topk_benchmark_no_major_regression():
    rng = np.random.default_rng(7)
    sims = rng.random(20000, dtype=np.float32)
    k = 250

    loops = 80
    t0 = time.perf_counter()
    for _ in range(loops):
        _old_topk(sims, k)
    old_elapsed = time.perf_counter() - t0

    t1 = time.perf_counter()
    for _ in range(loops):
        _new_topk(sims, k)
    new_elapsed = time.perf_counter() - t1

    # Conservative threshold to avoid flaky CI while still catching major regressions.
    assert new_elapsed <= (old_elapsed * 1.25)
