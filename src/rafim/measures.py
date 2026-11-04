"""Vertical bitsets and the support measures sup, rsup and rr.

A tid bitset packs the baskets that contain an item into uint64 words, so the baskets
containing an itemset are the AND of its items' bitsets and the count is a popcount.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse

MEASURES = ("standard", "retained")


def item_bitsets(m: sparse.csr_matrix) -> np.ndarray:
    """Return an (n_items, n_words) uint64 array of tid bitsets for a basket matrix."""
    n_baskets, n_items = m.shape
    n_words = max(1, (n_baskets + 63) // 64)
    out = np.zeros((n_items, n_words), dtype=np.uint64)
    coo = m.tocoo()
    words = coo.row // 64
    bits = np.left_shift(np.uint64(1), (coo.row % 64).astype(np.uint64))
    np.bitwise_or.at(out, (coo.col, words), bits)
    return out


def popcount(bits: np.ndarray) -> np.ndarray | int:
    """Count set bits along the last axis."""
    c = np.bitwise_count(bits).sum(axis=-1, dtype=np.int64)
    return int(c) if np.ndim(c) == 0 else c


def is_frequent(count: int | np.ndarray, n: int, minsup: float):
    """Frequency test used by every miner: count / n >= minsup (same rule as mlxtend)."""
    return np.asarray(count) / n >= minsup


def itemset_count(bits: np.ndarray, itemset) -> int:
    """Return the number of baskets that contain every item of itemset."""
    items = list(itemset)
    acc = bits[items[0]].copy()
    for i in items[1:]:
        acc &= bits[i]
    return popcount(acc)


def counts_for(bits: np.ndarray, itemsets) -> dict[tuple, int]:
    """Count many itemsets, reusing prefix bitsets level by level.

    Input: item bitsets and an iterable of sorted item-id tuples whose prefixes are
    also in the iterable or are single items. Output: {itemset: count}.
    """
    by_len: dict[int, list[tuple]] = {}
    for s in itemsets:
        by_len.setdefault(len(s), []).append(tuple(s))
    out: dict[tuple, int] = {}
    prev: dict[tuple, np.ndarray] = {}
    for k in sorted(by_len):
        cur: dict[tuple, np.ndarray] = {}
        for s in by_len[k]:
            if k == 1:
                acc = bits[s[0]]
            else:
                base = prev.get(s[:-1])
                if base is None:
                    base = bits[s[0]].copy()
                    for i in s[1:-1]:
                        base = base & bits[i]
                acc = base & bits[s[-1]]
            cur[s] = acc
            out[s] = popcount(acc)
        prev = cur
    return out


def return_rate(sup_count: int, rsup_count: int) -> float:
    """rr(X) = 1 - rsup(X) / sup(X)."""
    return 1.0 - rsup_count / sup_count if sup_count else float("nan")
