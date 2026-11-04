"""Link cancellation lines to the purchase lines they reverse.

Rule (CLAUDE.md section 4.5): for each cancellation line (customer c, stock s, date d,
quantity q), allocate |q| to purchase items of the same customer and stock code dated
strictly before d, starting from the most recent and walking backwards until |q| is used
up. A purchase item is one (invoice, stock_code) pair. Its capacity is the summed
purchased quantity minus what earlier cancellations already took. Cancellations are
processed in date order so that earlier returns consume capacity first.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from rafim.paths import PROCESSED, write_log

POLICIES = ("full", "any")


def purchase_items(purchases: pd.DataFrame) -> pd.DataFrame:
    """Aggregate purchase lines to one row per (invoice, stock_code).

    Output columns: invoice, stock_code, customer_id, invoice_date, quantity.
    """
    return (
        purchases.groupby(["invoice", "stock_code"], as_index=False, sort=False)
        .agg(customer_id=("customer_id", "first"), invoice_date=("invoice_date", "first"),
             quantity=("quantity", "sum"))
    )


def link(purchases: pd.DataFrame, cancels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate cancelled quantities to earlier purchases.

    Input: purchase lines and cancellation lines (quantity < 0).
    Output: (allocations, cancellation_status).
      allocations: cancel_row, cancel_invoice, purchase_invoice, stock_code, customer_id,
        quantity, purchase_date, cancel_date, lag_days.
      cancellation_status: one row per cancellation line with status
        'linked', 'partially_linked' or 'unlinked', a reason, and allocated quantity.
    """
    items = purchase_items(purchases.loc[purchases.customer_id.notna()])
    items = items.sort_values("invoice_date", kind="stable")
    # (customer, stock) -> list of [date, invoice, remaining capacity], ascending by date.
    index: dict[tuple, list] = defaultdict(list)
    for cust, stock, date, inv, qty in zip(
        items.customer_id, items.stock_code, items.invoice_date, items.invoice, items.quantity
    ):
        index[(cust, stock)].append([date, inv, int(qty)])

    order = cancels.assign(_row=np.arange(len(cancels))).sort_values(
        ["invoice_date", "_row"], kind="stable"
    )
    allocations = []
    status = []
    for row, inv, cust, stock, date, qty in zip(
        order._row, order.invoice, order.customer_id, order.stock_code,
        order.invoice_date, order.quantity
    ):
        need = -int(qty)
        if pd.isna(cust):
            status.append((row, "unlinked", "no_customer", 0, need))
            continue
        cands = index.get((cust, stock), [])
        earlier = [c for c in cands if c[0] < date]
        if not earlier:
            reason = "no_purchase_of_code" if not cands else "no_earlier_purchase"
            status.append((row, "unlinked", reason, 0, need))
            continue
        got = 0
        for cand in reversed(earlier):
            if need == 0:
                break
            take = min(need, cand[2])
            if take <= 0:
                continue
            cand[2] -= take
            need -= take
            got += take
            allocations.append((row, inv, cand[1], stock, cust, take, cand[0], date))
        if got == 0:
            status.append((row, "unlinked", "earlier_purchases_already_used", 0, need))
        elif need > 0:
            status.append((row, "partially_linked", "quantity_exceeds_earlier_purchases", got, need))
        else:
            status.append((row, "linked", "", got, 0))

    alloc = pd.DataFrame(
        allocations,
        columns=["cancel_row", "cancel_invoice", "purchase_invoice", "stock_code",
                 "customer_id", "quantity", "purchase_date", "cancel_date"],
    )
    for c in ("purchase_date", "cancel_date"):
        alloc[c] = pd.to_datetime(alloc[c])
    alloc["quantity"] = alloc.quantity.astype("int64")
    alloc["lag_days"] = (alloc.cancel_date - alloc.purchase_date).dt.total_seconds() / 86400
    stat = pd.DataFrame(status, columns=["cancel_row", "status", "reason", "allocated",
                                         "unallocated"]).sort_values("cancel_row")
    return alloc, stat.reset_index(drop=True)


def returned_items(purchases: pd.DataFrame, alloc: pd.DataFrame, policy: str) -> pd.DataFrame:
    """Mark purchase items as returned under a partial-return policy.

    policy 'full': returned when allocated quantity >= purchased quantity.
    policy 'any': returned when any quantity was allocated.
    Output: purchase items with columns allocated and returned (bool).
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}")
    items = purchase_items(purchases)
    got = alloc.groupby(["purchase_invoice", "stock_code"]).quantity.sum().rename("allocated")
    items = items.merge(got, left_on=["invoice", "stock_code"], right_index=True, how="left")
    items["allocated"] = items.allocated.fillna(0).astype("int64")
    if policy == "full":
        items["returned"] = items.allocated >= items.quantity
    else:
        items["returned"] = items.allocated > 0
    return items


def summarize(purchases: pd.DataFrame, cancels: pd.DataFrame, alloc: pd.DataFrame,
              stat: pd.DataFrame) -> dict:
    """Build the linking log: status counts, reasons, lag distribution, affected shares."""
    log: dict = {
        "cancellation_lines": len(stat),
        "status_counts": stat.status.value_counts().to_dict(),
        "reason_counts": stat.loc[stat.status != "linked"].groupby(["status", "reason"]).size()
        .rename("n").reset_index().to_dict("records"),
        "cancelled_quantity_total": int(-cancels.quantity.sum()),
        "allocated_quantity_total": int(alloc.quantity.sum()),
        "allocations": len(alloc),
        "cancellation_lines_split_over_multiple_purchases": int(
            (alloc.groupby("cancel_row").size() > 1).sum()
        ),
    }
    lag = alloc.lag_days
    qs = [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    log["lag_days_allocation_weighted_by_line"] = {
        "count": len(lag), "mean": float(lag.mean()), "min": float(lag.min()),
        "max": float(lag.max()), **{f"q{int(q * 100)}": float(lag.quantile(q)) for q in qs},
    }
    for d in (1, 7, 30, 90, 180, 365):
        log["lag_days_allocation_weighted_by_line"][f"share_le_{d}d"] = float((lag <= d).mean())
    scoped = purchases.loc[purchases.customer_id.notna()]
    n_baskets = scoped.invoice.nunique()
    for policy in POLICIES:
        it = returned_items(scoped, alloc, policy)
        log[f"policy_{policy}"] = {
            "basket_items": len(it),
            "items_returned": int(it.returned.sum()),
            "item_return_rate": float(it.returned.mean()),
            "baskets": n_baskets,
            "baskets_with_a_returned_item": int(it.loc[it.returned].invoice.nunique()),
            "share_baskets_affected": float(it.loc[it.returned].invoice.nunique() / n_baskets),
            "items_with_partial_allocation": int(((it.allocated > 0) & (it.allocated < it.quantity)).sum()),
        }
    return log


def run() -> pd.DataFrame:
    """Link returns on the full cleaned dataset and write outputs and the log."""
    purchases = pd.read_parquet(PROCESSED / "purchases.parquet")
    cancels = pd.read_parquet(PROCESSED / "cancellations.parquet")
    alloc, stat = link(purchases, cancels)
    alloc.to_parquet(PROCESSED / "allocations.parquet", index=False)
    stat.to_parquet(PROCESSED / "cancellation_status.parquet", index=False)
    write_log("04_link_returns", summarize(purchases, cancels, alloc, stat))
    return alloc


if __name__ == "__main__":
    import json

    from rafim.paths import LOGS
    run()
    print(json.dumps(json.loads((LOGS / "04_link_returns.json").read_text()), indent=1))
