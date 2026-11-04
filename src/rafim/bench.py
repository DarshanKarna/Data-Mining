"""Timing and memory measurement for the miners (E1, E2, E7).

Timing: time.perf_counter, repeated runs, median and spread.
Memory: tracemalloc peak of Python and NumPy allocations during one separate run
(tracemalloc slows code down, so it is never active during timed runs).
"""

from __future__ import annotations

import gc
import statistics
import time
import tracemalloc
from collections.abc import Callable

import pandas as pd
from mlxtend.frequent_patterns import apriori as mx_apriori
from mlxtend.frequent_patterns import fpgrowth as mx_fpgrowth

from rafim.apriori import apriori
from rafim.baskets import Baskets
from rafim.fpgrowth import fpgrowth
from rafim.measures import item_bitsets


class Miner:
    """Holds precomputed inputs for one basket set so timed runs exclude preparation."""

    def __init__(self, b: Baskets):
        self.n = b.n
        self.full_bits = item_bitsets(b.full)
        self.kept_bits = item_bitsets(b.kept)
        self.full_lists = b.lists("full")
        self.kept_lists = b.lists("kept")
        self.full_matrix = b.full

    def run(self, algo: str, measure: str, minsup: float) -> dict:
        """Run one of our miners. Output: {itemset: (full_count, kept_count or None)}."""
        if algo == "apriori":
            return apriori(self.full_bits, self.kept_bits, self.n, minsup, measure)
        return fpgrowth(self.full_lists, self.kept_lists, self.full_bits, self.n, minsup,
                        measure)

    def run_mlxtend(self, algo: str, minsup: float) -> pd.DataFrame:
        """Run mlxtend (standard support only) on a sparse DataFrame of full baskets."""
        df = pd.DataFrame.sparse.from_spmatrix(self.full_matrix,
                                               columns=list(range(self.full_matrix.shape[1])))
        fn = mx_apriori if algo == "apriori" else mx_fpgrowth
        kwargs = {"low_memory": True} if algo == "apriori" else {}
        return fn(df, min_support=minsup, **kwargs)


def time_runs(fn: Callable[[], object], repeats: int) -> tuple[list[float], object]:
    """Call fn `repeats` times. Output: (list of seconds, result of the last call)."""
    times, result = [], None
    for _ in range(repeats):
        gc.collect()
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return times, result


def peak_memory_mb(fn: Callable[[], object]) -> float:
    """Return the tracemalloc peak in MiB for one call of fn."""
    gc.collect()
    tracemalloc.start()
    try:
        fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak / 2**20


def summarize_times(times: list[float]) -> dict:
    """Median, min, max and IQR of a list of runtimes in seconds."""
    q = statistics.quantiles(times, n=4) if len(times) >= 2 else [times[0]] * 3
    return {"runtime_median_s": statistics.median(times), "runtime_min_s": min(times),
            "runtime_max_s": max(times), "runtime_iqr_s": q[2] - q[0],
            "repeats": len(times)}
