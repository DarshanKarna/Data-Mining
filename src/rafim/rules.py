"""Association rules with conf, rconf, lift and rr.

lift follows the measure of the run: baseline lift = conf / sup(B),
return-aware lift = rconf / rsup(B).
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from rafim.measures import counts_for


def fill_counts(itemsets: dict[tuple, tuple], full_bits: np.ndarray,
                kept_bits: np.ndarray) -> dict[tuple, tuple[int, int]]:
    """Return {itemset: (full_count, kept_count)}, computing any missing count from bitsets."""
    need_full = [s for s, (f, _) in itemsets.items() if f is None]
    need_kept = [s for s, (_, k) in itemsets.items() if k is None]
    fc = counts_for(full_bits, need_full) if need_full else {}
    kc = counts_for(kept_bits, need_kept) if need_kept else {}
    return {s: (f if f is not None else fc[s], k if k is not None else kc[s])
            for s, (f, k) in itemsets.items()}


def generate(itemsets: dict[tuple, tuple[int, int]], n: int, measure: str,
             min_conf: float) -> pd.DataFrame:
    """Generate rules A => B from frequent itemsets.

    Input: itemsets with both counts (every subset of a listed itemset must be listed),
    number of baskets, measure ('standard' or 'retained'), minimum confidence under that
    measure. Output: rules ranked by confidence under the measure, then lift, then support.
    """
    rows = []
    retained = measure == "retained"
    for s, (fx, kx) in itemsets.items():
        if len(s) < 2:
            continue
        for r in range(1, len(s)):
            for a in combinations(s, r):
                b = tuple(i for i in s if i not in a)
                fa, ka = itemsets[a]
                fb, kb = itemsets[b]
                conf = fx / fa
                rconf = kx / ka if ka else float("nan")
                score = rconf if retained else conf
                if not score >= min_conf:
                    continue
                lift = rconf / (kb / n) if retained else conf / (fb / n)
                rows.append((a, b, fx / n, kx / n, conf, rconf, lift,
                             1 - kx / fx if fx else float("nan")))
    cols = ["antecedent", "consequent", "sup", "rsup", "conf", "rconf", "lift", "rr"]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    key = "rconf" if retained else "conf"
    supp = "rsup" if retained else "sup"
    df["rule_key"] = [f"{a}->{b}" for a, b in zip(df.antecedent, df.consequent)]
    df = df.sort_values([key, "lift", supp, "rule_key"],
                        ascending=[False, False, False, True], kind="stable")
    return df.reset_index(drop=True)
