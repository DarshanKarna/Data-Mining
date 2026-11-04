"""Build purchase baskets t and kept baskets k(t) as sparse matrices.

One basket per purchase invoice. Items are stock codes. k(t) holds the items of t that
are not marked returned under the chosen partial-return policy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from rafim.link_returns import returned_items

TRAIN_START = pd.Timestamp("2009-12-01")
HOLDOUT_START = pd.Timestamp("2010-12-01")


@dataclass
class Baskets:
    """Full and kept baskets over a fixed item vocabulary.

    full, kept: CSR boolean matrices (n_baskets x n_items).
    meta: one row per basket (invoice, invoice_date, customer_id, anonymous).
    items: stock code per column.
    """

    full: sparse.csr_matrix
    kept: sparse.csr_matrix
    meta: pd.DataFrame
    items: np.ndarray

    @property
    def n(self) -> int:
        """Number of baskets."""
        return self.full.shape[0]

    def subset(self, mask: np.ndarray) -> Baskets:
        """Return the baskets selected by a boolean mask, keeping the item vocabulary."""
        idx = np.flatnonzero(mask)
        return Baskets(self.full[idx], self.kept[idx], self.meta.iloc[idx].reset_index(drop=True),
                       self.items)

    def lists(self, which: str = "full") -> list[np.ndarray]:
        """Return each basket as an array of item ids ('full' or 'kept')."""
        m = self.full if which == "full" else self.kept
        return [m.indices[m.indptr[i]:m.indptr[i + 1]] for i in range(m.shape[0])]


def build(purchases: pd.DataFrame, alloc: pd.DataFrame, policy: str,
          include_anonymous: bool) -> Baskets:
    """Build baskets from purchase lines and return allocations.

    Input: cleaned purchase lines, allocation table, policy ('full' or 'any'), and whether
    to include purchases without a Customer ID (their kept basket equals the full basket).
    Output: Baskets.
    """
    scope = purchases if include_anonymous else purchases.loc[purchases.customer_id.notna()]
    items = returned_items(scope, alloc, policy)
    meta = (
        scope.groupby("invoice", sort=False)
        .agg(invoice_date=("invoice_date", "first"), customer_id=("customer_id", "first"))
        .reset_index()
        .sort_values(["invoice_date", "invoice"], kind="stable")
        .reset_index(drop=True)
    )
    meta["anonymous"] = meta.customer_id.isna()
    vocab = np.array(sorted(items.stock_code.unique()))
    col = pd.Series(np.arange(len(vocab)), index=vocab)
    row = pd.Series(np.arange(len(meta)), index=meta.invoice)
    r = row.loc[items.invoice].to_numpy()
    c = col.loc[items.stock_code].to_numpy()
    shape = (len(meta), len(vocab))
    full = sparse.csr_matrix((np.ones(len(r), dtype=bool), (r, c)), shape=shape)
    keep = ~items.returned.to_numpy()
    kept = sparse.csr_matrix((np.ones(keep.sum(), dtype=bool), (r[keep], c[keep])), shape=shape)
    full.sort_indices()
    kept.sort_indices()
    return Baskets(full, kept, meta, vocab)


def time_split(b: Baskets) -> tuple[Baskets, Baskets]:
    """Split into train (2009-12-01 to 2010-11-30) and hold-out (2010-12-01 onwards)."""
    d = b.meta.invoice_date
    train = (d >= TRAIN_START) & (d < HOLDOUT_START)
    return b.subset(train.to_numpy()), b.subset((d >= HOLDOUT_START).to_numpy())
