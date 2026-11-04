"""Comparisons between baseline and return-aware output (E3, E4, E5, E6)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from rafim.baskets import Baskets
from rafim.measures import item_bitsets, itemset_count


def with_codes(rules: pd.DataFrame, items: np.ndarray) -> pd.DataFrame:
    """Add stock-code columns and a code-based rule key (stable across vocabularies)."""
    out = rules.copy()
    out["a_codes"] = [tuple(items[list(a)]) for a in out.antecedent]
    out["b_codes"] = [tuple(items[list(b)]) for b in out.consequent]
    out["key"] = [",".join(a) + "=>" + ",".join(b) for a, b in zip(out.a_codes, out.b_codes)]
    return out


def output_change(base_sets: dict, ra_sets: dict, base_rules: pd.DataFrame,
                  ra_rules: pd.DataFrame, top_k: list[int]) -> dict:
    """E3: itemsets and rules that appear or disappear, top-k overlap, Kendall tau.

    Kendall tau-b is computed between conf and rconf over the rules found by both runs.
    """
    b, r = set(base_sets), set(ra_sets)
    bk, rk = set(base_rules.key), set(ra_rules.key)
    out = {
        "itemsets_baseline": len(b), "itemsets_return_aware": len(r),
        "itemsets_only_baseline": len(b - r), "itemsets_only_return_aware": len(r - b),
        "itemsets_both": len(b & r),
        "rules_baseline": len(bk), "rules_return_aware": len(rk),
        "rules_only_baseline": len(bk - rk), "rules_only_return_aware": len(rk - bk),
        "rules_both": len(bk & rk),
    }
    for k in top_k:
        tb, tr = list(base_rules.key[:k]), list(ra_rules.key[:k])
        denom = min(k, len(tb), len(tr))
        out[f"top{k}_overlap"] = len(set(tb) & set(tr)) / denom if denom else np.nan
    common = base_rules.loc[base_rules.key.isin(rk), ["key", "conf", "rconf"]]
    if len(common) >= 3:
        tau = kendalltau(common.conf, common.rconf)
        out["kendall_tau_common_rules"] = float(tau.statistic)
        out["kendall_p_common_rules"] = float(tau.pvalue)
        out["kendall_n"] = len(common)
    else:
        out.update(kendall_tau_common_rules=np.nan, kendall_p_common_rules=np.nan,
                   kendall_n=len(common))
    return out


def line_return_rate(b: Baskets) -> float:
    """Share of basket items (invoice, stock code) marked returned: 1 - nnz(kept)/nnz(full)."""
    return 1.0 - b.kept.nnz / b.full.nnz


def holdout_stability(rules: pd.DataFrame, train_score: str, hold: Baskets,
                      min_conf: float, k: int) -> dict:
    """E5: evaluate the top-k train rules on hold-out kept baskets.

    Input: rules ranked for one run, the train confidence column of that run ('conf' or
    'rconf'), hold-out baskets (same vocabulary), min_conf, k.
    Output: share of rules whose hold-out rconf >= min_conf, mean change in confidence,
    and per-rule values.
    """
    top = rules.head(k)
    kb, fb = item_bitsets(hold.kept), item_bitsets(hold.full)
    vals, conf_h = [], []
    for a, b in zip(top.antecedent, top.consequent):
        s = tuple(sorted(a + b))
        ka = itemset_count(kb, a)
        vals.append(itemset_count(kb, s) / ka if ka else np.nan)
        fa = itemset_count(fb, a)
        conf_h.append(itemset_count(fb, s) / fa if fa else np.nan)
    vals = np.array(vals, dtype=float)
    delta = vals - top[train_score].to_numpy()
    return {
        "k": len(top),
        "share_meeting_min_conf": float(np.mean(np.nan_to_num(vals, nan=-1) >= min_conf)),
        "mean_rconf_holdout": float(np.nanmean(vals)) if len(vals) else np.nan,
        "mean_change_in_confidence": float(np.nanmean(delta)) if len(vals) else np.nan,
        "rules_with_antecedent_absent": int(np.isnan(vals).sum()),
        "per_rule": pd.DataFrame({"key": top.key.to_numpy(), "train_conf": top[train_score],
                                  "holdout_rconf": vals, "holdout_conf": conf_h}),
    }


def descriptions(purchases: pd.DataFrame) -> pd.Series:
    """Most frequent description per stock code."""
    return (purchases.groupby("stock_code").description
            .agg(lambda s: s.value_counts().index[0]))


def label(codes: tuple, desc: pd.Series) -> str:
    """Join product descriptions of a code tuple for tables."""
    return " + ".join(desc.get(c, c) for c in codes)
