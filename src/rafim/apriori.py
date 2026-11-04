"""Apriori with vertical bitset counting and a measure switch.

standard: prune on sup, count only full baskets.
retained: count full and kept baskets in the same pass, prune on rsup.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from rafim.measures import MEASURES, is_frequent, popcount


def apriori(full_bits: np.ndarray, kept_bits: np.ndarray | None, n: int, minsup: float,
            measure: str = "standard", max_len: int | None = None) -> dict[tuple, tuple]:
    """Mine frequent itemsets level by level.

    Input: item bitsets of full baskets and (for retained) kept baskets, number of
    baskets n, minimum support as a fraction, measure, optional max itemset length.
    Output: {sorted item-id tuple: (full_count, kept_count or None)}.
    """
    if measure not in MEASURES:
        raise ValueError(measure)
    retained = measure == "retained"
    prune_bits = kept_bits if retained else full_bits
    out: dict[tuple, tuple] = {}

    c1 = popcount(prune_bits)
    level_items = np.flatnonzero(is_frequent(c1, n, minsup))
    # current level: itemset -> (prune bitset, full bitset or None)
    level: dict[tuple, tuple] = {}
    full_c1 = popcount(full_bits) if retained else None
    for i in level_items:
        s = (int(i),)
        level[s] = (prune_bits[i], full_bits[i] if retained else None)
        out[s] = (int(full_c1[i]), int(c1[i])) if retained else (int(c1[i]), None)

    k = 1
    while level and (max_len is None or k < max_len):
        k += 1
        frequent_prev = set(level)
        groups: dict[tuple, list[int]] = {}
        for s in level:
            groups.setdefault(s[:-1], []).append(s[-1])
        nxt: dict[tuple, tuple] = {}
        for prefix, lasts in groups.items():
            lasts.sort()
            for ai, a in enumerate(lasts):
                left = prefix + (a,)
                bs = []
                for b in lasts[ai + 1:]:
                    cand = left + (b,)
                    if k > 2 and any(
                        sub not in frequent_prev for sub in combinations(cand, k - 1)
                    ):
                        continue
                    bs.append(b)
                if not bs:
                    continue
                pb, fb = level[left]
                cand_prune = pb[None, :] & prune_bits[bs]
                cnt = popcount(cand_prune)
                if retained:
                    cand_full = fb[None, :] & full_bits[bs]
                    fcnt = popcount(cand_full)
                keep = np.flatnonzero(is_frequent(cnt, n, minsup))
                if not len(keep):
                    continue
                # Copy only surviving rows so the full candidate block can be freed.
                kp = cand_prune[keep]
                kf = cand_full[keep] if retained else None
                for r, j in enumerate(keep):
                    s = left + (bs[j],)
                    if retained:
                        nxt[s] = (kp[r], kf[r])
                        out[s] = (int(fcnt[j]), int(cnt[j]))
                    else:
                        nxt[s] = (kp[r], None)
                        out[s] = (int(cnt[j]), None)
        level = nxt
    return out
