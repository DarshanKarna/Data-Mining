"""Hand-built linking cases (CLAUDE.md section 5)."""

from __future__ import annotations

import pandas as pd

from rafim.link_returns import link, returned_items


def P(inv, cust, stock, qty, date):
    return {"invoice": inv, "customer_id": cust, "stock_code": stock, "quantity": qty,
            "invoice_date": pd.Timestamp(date), "description": "x", "price": 1.0,
            "country": "UK"}


def C(inv, cust, stock, qty, date):
    return P(inv, cust, stock, -abs(qty), date)


def frames(purchases, cancels):
    return pd.DataFrame(purchases), pd.DataFrame(cancels)


def test_multiple_purchases_most_recent_first():
    p, c = frames(
        [P("1", "A", "X", 5, "2010-01-01"), P("2", "A", "X", 5, "2010-02-01")],
        [C("C1", "A", "X", 3, "2010-03-01")],
    )
    alloc, stat = link(p, c)
    assert list(alloc.purchase_invoice) == ["2"]
    assert alloc.quantity.sum() == 3
    assert stat.status[0] == "linked"


def test_return_larger_than_single_line_walks_back():
    p, c = frames(
        [P("1", "A", "X", 4, "2010-01-01"), P("2", "A", "X", 2, "2010-02-01")],
        [C("C1", "A", "X", 5, "2010-03-01")],
    )
    alloc, stat = link(p, c)
    assert dict(zip(alloc.purchase_invoice, alloc.quantity)) == {"2": 2, "1": 3}
    assert stat.status[0] == "linked"


def test_return_larger_than_all_purchases_is_partial():
    p, c = frames([P("1", "A", "X", 2, "2010-01-01")], [C("C1", "A", "X", 5, "2010-03-01")])
    alloc, stat = link(p, c)
    assert alloc.quantity.sum() == 2
    assert stat.status[0] == "partially_linked"
    assert stat.unallocated[0] == 3


def test_partial_return_policies():
    p, c = frames(
        [P("1", "A", "X", 10, "2010-01-01"), P("1", "A", "Y", 2, "2010-01-01")],
        [C("C1", "A", "X", 4, "2010-02-01"), C("C1", "A", "Y", 2, "2010-02-01")],
    )
    alloc, _ = link(p, c)
    full = returned_items(p, alloc, "full").set_index("stock_code").returned
    any_ = returned_items(p, alloc, "any").set_index("stock_code").returned
    assert not full["X"] and full["Y"]
    assert any_["X"] and any_["Y"]


def test_cancellation_before_any_purchase_is_unlinked():
    p, c = frames([P("1", "A", "X", 5, "2010-05-01")], [C("C1", "A", "X", 1, "2010-03-01")])
    alloc, stat = link(p, c)
    assert alloc.empty
    assert (stat.status[0], stat.reason[0]) == ("unlinked", "no_earlier_purchase")


def test_same_timestamp_is_not_earlier():
    p, c = frames([P("1", "A", "X", 5, "2010-03-01")], [C("C1", "A", "X", 1, "2010-03-01")])
    _, stat = link(p, c)
    assert stat.status[0] == "unlinked"


def test_missing_customer_is_unlinked():
    p, c = frames([P("1", "A", "X", 5, "2010-01-01")], [C("C1", None, "X", 1, "2010-03-01")])
    alloc, stat = link(p, c)
    assert alloc.empty
    assert stat.reason[0] == "no_customer"


def test_other_customer_or_code_not_linked():
    p, c = frames(
        [P("1", "B", "X", 5, "2010-01-01"), P("2", "A", "Y", 5, "2010-01-01")],
        [C("C1", "A", "X", 1, "2010-03-01")],
    )
    alloc, stat = link(p, c)
    assert alloc.empty
    assert stat.reason[0] == "no_purchase_of_code"


def test_capacity_shared_between_cancellations():
    p, c = frames(
        [P("1", "A", "X", 3, "2010-01-01")],
        [C("C1", "A", "X", 2, "2010-02-01"), C("C2", "A", "X", 2, "2010-03-01")],
    )
    alloc, stat = link(p, c)
    assert alloc.quantity.sum() == 3
    assert list(stat.status) == ["linked", "partially_linked"]
