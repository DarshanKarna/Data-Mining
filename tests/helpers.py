"""Shared helpers for tests: build bitsets from basket lists and run every miner."""

from __future__ import annotations

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import apriori as mx_apriori
from mlxtend.frequent_patterns import fpgrowth as mx_fpgrowth
from scipy import sparse

from rafim.apriori import apriori
from rafim.fpgrowth import fpgrowth
from rafim.measures import item_bitsets


def to_csr(baskets: list[list[int]], n_items: int) -> sparse.csr_matrix:
    """Convert lists of item ids to a CSR boolean matrix."""
    rows = [i for i, t in enumerate(baskets) for _ in set(t)]
    cols = [c for t in baskets for c in sorted(set(t))]
    m = sparse.csr_matrix((np.ones(len(rows), dtype=bool), (rows, cols)),
                          shape=(len(baskets), n_items))
    m.sort_indices()
    return m


def run_all(full: sparse.csr_matrix, kept: sparse.csr_matrix, minsup: float, measure: str,
            max_len=None) -> tuple[dict, dict]:
    """Run our Apriori and FP-Growth on matrices. Output: (apriori_result, fpgrowth_result)."""
    fb, kb = item_bitsets(full), item_bitsets(kept)
    n = full.shape[0]
    ap = apriori(fb, kb, n, minsup, measure, max_len)
    lists = lambda m: [m.indices[m.indptr[i]:m.indptr[i + 1]] for i in range(m.shape[0])]
    fp = fpgrowth(lists(full), lists(kept), fb, n, minsup, measure, max_len)
    return ap, fp


def run_mlxtend(full: sparse.csr_matrix, minsup: float, algo: str, max_len=None) -> dict:
    """Run mlxtend on a sparse DataFrame. Output: {itemset tuple: count}."""
    df = pd.DataFrame.sparse.from_spmatrix(full.astype(bool),
                                           columns=list(range(full.shape[1])))
    fn = mx_apriori if algo == "apriori" else mx_fpgrowth
    res = fn(df, min_support=minsup, use_colnames=True, max_len=max_len)
    n = full.shape[0]
    return {tuple(sorted(s)): round(v * n) for s, v in zip(res.itemsets, res.support)}
