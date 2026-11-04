"""Correctness gates for Apriori and FP-Growth (CLAUDE.md section 5)."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from helpers import run_all, run_mlxtend, to_csr
from rafim.measures import item_bitsets, itemset_count

TOY = [[0, 1, 2], [0, 1], [0, 2, 3], [1, 2], [0, 1, 2, 3], [3], [0, 1, 3], [1, 2, 3]]
TOY_KEPT = [[0, 1], [0, 1], [0, 3], [1, 2], [0, 1, 2], [], [0, 1, 3], [2, 3]]


def std_counts(res: dict) -> dict:
    return {s: f for s, (f, _) in res.items()}


@pytest.mark.parametrize("minsup", [0.125, 0.25, 0.375, 0.5])
def test_standard_matches_mlxtend_on_toy(minsup):
    full = to_csr(TOY, 4)
    ap, fp = run_all(full, full, minsup, "standard")
    mx_a = run_mlxtend(full, minsup, "apriori")
    mx_f = run_mlxtend(full, minsup, "fpgrowth")
    assert std_counts(ap) == mx_a == mx_f == std_counts(fp)


def test_toy_hand_counts():
    full = to_csr(TOY, 4)
    ap, _ = run_all(full, full, 0.375, "standard")
    # {0,1}: baskets 0,1,4,6 -> 4 of 8
    assert ap[(0, 1)][0] == 4
    assert (0, 1, 2) not in ap  # baskets 0,4 -> 2 of 8 < 3


@pytest.mark.parametrize("minsup", [0.125, 0.25, 0.375])
def test_retained_equals_standard_without_returns(minsup):
    full = to_csr(TOY, 4)
    ap_s, fp_s = run_all(full, full, minsup, "standard")
    ap_r, fp_r = run_all(full, full, minsup, "retained")
    assert std_counts(ap_s) == std_counts(ap_r) == std_counts(fp_r) == std_counts(fp_s)
    assert all(f == k for f, k in ap_r.values())
    assert all(f == k for f, k in fp_r.values())


@pytest.mark.parametrize("minsup", [0.125, 0.25, 0.375])
def test_retained_apriori_equals_fpgrowth_toy(minsup):
    full, kept = to_csr(TOY, 4), to_csr(TOY_KEPT, 4)
    ap, fp = run_all(full, kept, minsup, "retained")
    assert ap == fp
    kb = item_bitsets(kept)
    for s, (_, k) in ap.items():
        assert k == itemset_count(kb, s)
        assert k / 8 >= minsup


def _random_baskets(draw):
    n_items = draw(st.integers(2, 8))
    n = draw(st.integers(1, 40))
    full, kept = [], []
    for _ in range(n):
        t = draw(st.lists(st.integers(0, n_items - 1), max_size=n_items, unique=True))
        drop = draw(st.lists(st.booleans(), min_size=len(t), max_size=len(t)))
        full.append(t)
        kept.append([i for i, d in zip(t, drop) if not d])
    return n_items, full, kept


@st.composite
def basket_sets(draw):
    return _random_baskets(draw)


@settings(max_examples=150, deadline=None)
@given(basket_sets(), st.sampled_from([0.05, 0.1, 0.2, 0.3]))
def test_property_rsup_antimonotone_and_bounded(data, minsup):
    n_items, full, kept = data
    f, k = to_csr(full, n_items), to_csr(kept, n_items)
    ap, fp = run_all(f, k, minsup, "retained")
    assert ap == fp
    kb = item_bitsets(k)
    for s, (fc, kc) in ap.items():
        assert kc <= fc  # rsup <= sup
        for i in range(len(s)):
            sub = s[:i] + s[i + 1:]
            if sub:
                assert itemset_count(kb, sub) >= kc  # anti-monotone
                assert sub in ap  # downward closure of the output
    # Completeness: every itemset of size <= 2 meeting minsup on kept baskets is reported.
    for a in range(n_items):
        for b in range(a, n_items):
            s = (a,) if a == b else (a, b)
            if itemset_count(kb, s) / len(full) >= minsup:
                assert s in ap


@settings(max_examples=60, deadline=None)
@given(basket_sets(), st.sampled_from([0.1, 0.2, 0.3]))
def test_property_standard_matches_mlxtend(data, minsup):
    n_items, full, _ = data
    f = to_csr(full, n_items)
    if f.nnz == 0:
        return
    ap, fp = run_all(f, f, minsup, "standard")
    assert std_counts(ap) == std_counts(fp) == run_mlxtend(f, minsup, "fpgrowth")


def test_bitsets_cross_word_boundary():
    rng = np.random.default_rng(0)
    baskets = [list(rng.choice(5, size=rng.integers(1, 4), replace=False)) for _ in range(200)]
    f = to_csr(baskets, 5)
    fb = item_bitsets(f)
    dense = f.toarray()
    assert itemset_count(fb, (1, 3)) == int((dense[:, 1] & dense[:, 3]).sum())
