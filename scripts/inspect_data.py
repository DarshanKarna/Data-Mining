"""Inspect the normalised dataset and write evidence to results/logs/02_inspect.json.

Nothing here changes data. The output is used to decide cleaning rules.
"""

from __future__ import annotations

import re

import pandas as pd

from rafim.load import load
from rafim.paths import write_log

PRODUCT_CODE = re.compile(r"^\d{5}[A-Z]{0,2}$")


def main() -> None:
    """Print and log dataset facts used to design the cleaning step."""
    df = load()
    out: dict = {"rows": len(df)}
    out["date_min"] = df["invoice_date"].min()
    out["date_max"] = df["invoice_date"].max()
    out["per_sheet_date_range"] = {
        s: [g["invoice_date"].min(), g["invoice_date"].max()] for s, g in df.groupby("sheet")
    }

    # Overlap between sheets.
    s1, s2 = sorted(df["sheet"].unique())
    inv1 = set(df.loc[df.sheet == s1, "invoice"])
    inv2 = set(df.loc[df.sheet == s2, "invoice"])
    out["invoices_in_both_sheets"] = len(inv1 & inv2)
    key = ["invoice", "stock_code", "description", "quantity", "invoice_date", "price",
           "customer_id", "country"]
    out["exact_duplicate_rows_total"] = int(df.duplicated(key).sum())
    within = df.groupby("sheet", group_keys=False).apply(lambda g: g.duplicated(key))
    out["exact_duplicate_rows_within_sheet"] = int(within.sum())

    # Invoice prefixes.
    prefix = df["invoice"].str.extract(r"^([A-Z]*)", expand=False)
    out["invoice_prefix_counts"] = prefix.replace("", "<digits>").value_counts().to_dict()
    for p in prefix.unique():
        if p not in ("", "C"):
            out[f"rows_with_prefix_{p}"] = df.loc[prefix == p].head(10).to_dict("records")

    is_c = prefix == "C"
    out["quantity_sign"] = {
        "C_invoice_qty_neg": int((is_c & (df.quantity < 0)).sum()),
        "C_invoice_qty_pos": int((is_c & (df.quantity > 0)).sum()),
        "nonC_qty_pos": int((~is_c & (df.quantity > 0)).sum()),
        "nonC_qty_neg": int((~is_c & (df.quantity < 0)).sum()),
        "qty_zero": int((df.quantity == 0).sum()),
    }
    neg_nonc = df.loc[~is_c & (df.quantity < 0)]
    out["nonC_negative_qty_with_customer"] = int(neg_nonc.customer_id.notna().sum())
    out["nonC_negative_qty_price_zero"] = int((neg_nonc.price == 0).sum())
    out["nonC_negative_qty_top_descriptions"] = (
        neg_nonc.description.fillna("<NA>").value_counts().head(15).to_dict()
    )
    out["price_negative_rows"] = df.loc[df.price < 0].to_dict("records")
    out["price_zero_rows"] = int((df.price == 0).sum())

    out["missing"] = df[["description", "customer_id", "country"]].isna().sum().to_dict()
    out["missing_customer_by_type"] = {
        "purchase_rows": int((~is_c & df.customer_id.isna()).sum()),
        "cancellation_rows": int((is_c & df.customer_id.isna()).sum()),
    }

    # Candidate non-product stock codes: codes not shaped like 5 digits + up to 2 letters.
    odd = df.loc[~df.stock_code.str.match(PRODUCT_CODE)]
    cand = (
        odd.groupby("stock_code")
        .agg(rows=("invoice", "size"),
             descriptions=("description", lambda s: s.dropna().value_counts().head(3).to_dict()),
             median_price=("price", "median"))
        .sort_values("rows", ascending=False)
    )
    out["non_pattern_code_count"] = len(cand)
    out["non_pattern_codes"] = cand.reset_index().to_dict("records")

    # Codes with more than one description.
    nd = df.dropna(subset=["description"]).groupby("stock_code").description.nunique()
    out["codes_with_multiple_descriptions"] = int((nd > 1).sum())

    out["distinct"] = {
        "invoices": df.invoice.nunique(),
        "stock_codes": df.stock_code.nunique(),
        "customers": df.customer_id.nunique(),
        "countries": df.country.nunique(),
    }
    write_log("02_inspect", out)
    pd.set_option("display.width", 200)
    for k, v in out.items():
        if k in ("non_pattern_codes",):
            continue
        print(k, ":", v)
    print("\nnon-pattern codes:")
    for r in out["non_pattern_codes"]:
        print(f"  {r['stock_code']:<14} rows={r['rows']:<6} med_price={r['median_price']:<8} "
              f"{r['descriptions']}")


if __name__ == "__main__":
    main()
