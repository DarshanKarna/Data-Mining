"""Correctness gate on a seeded sample of the real train baskets (skipped without data)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from helpers import run_all, run_mlxtend
from rafim.baskets import build, time_split
from rafim.paths import PROCESSED

pytestmark = pytest.mark.skipif(
    not (PROCESSED / "allocations.parquet").exists(), reason="processed data not built"
)


@pytest.fixture(scope="module")
def sample():
    purchases = pd.read_parquet(PROCESSED / "purchases.parquet")
    alloc = pd.read_parquet(PROCESSED / "allocations.parquet")
    train, _ = time_split(build(purchases, alloc, "full", include_anonymous=False))
    rng = np.random.default_rng(42)
    idx = np.sort(rng.choice(train.n, size=3000, replace=False))
    mask = np.zeros(train.n, dtype=bool)
    mask[idx] = True
    return train.subset(mask)


@pytest.mark.parametrize("minsup", [0.03, 0.02, 0.015])
def test_standard_matches_mlxtend_on_real_sample(sample, minsup):
    ap, fp = run_all(sample.full, sample.kept, minsup, "standard")
    ours_a = {s: f for s, (f, _) in ap.items()}
    ours_f = {s: f for s, (f, _) in fp.items()}
    assert ours_a == ours_f
    assert ours_a == run_mlxtend(sample.full, minsup, "apriori")
    assert ours_a == run_mlxtend(sample.full, minsup, "fpgrowth")
    assert len(ours_a) > 20


@pytest.mark.parametrize("minsup", [0.02, 0.015, 0.01])
def test_retained_apriori_equals_fpgrowth_on_real_sample(sample, minsup):
    ap, fp = run_all(sample.full, sample.kept, minsup, "retained")
    assert ap == fp
    assert all(k <= f for f, k in ap.values())
