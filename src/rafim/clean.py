"""Clean the normalised dataset and split it into purchases and cancellations.

Every step logs the row count before and after to results/logs/03_clean.json.
"""

from __future__ import annotations

import pandas as pd
import yaml

from rafim.load import load
from rafim.paths import CONFIGS, PROCESSED, write_log

OVERLAP_SHEET = "Year 2009-2010"
LATER_SHEET = "Year 2010-2011"


def non_product_codes() -> set[str]:
    """Return the non-product stock codes listed in configs/non_product_codes.yaml."""
    data = yaml.safe_load((CONFIGS / "non_product_codes.yaml").read_text(encoding="utf-8"))
    return set(data["codes"])


def drop_sheet_overlap(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows of the earlier sheet whose invoice also appears in the later sheet.

    The two sheets both hold 2010-12-01..2010-12-09. Inspection showed those rows are
    identical in both sheets, so the earlier sheet's copy is removed.
    """
    later = set(df.loc[df.sheet == LATER_SHEET, "invoice"])
    dup = (df.sheet == OVERLAP_SHEET) & df.invoice.isin(later)
    return df.loc[~dup]


def invoice_type(invoice: pd.Series) -> pd.Series:
    """Map invoice numbers to 'purchase' (digits), 'cancellation' (C...) or 'other'."""
    prefix = invoice.str.extract(r"^([A-Z]*)", expand=False)
    return prefix.map(lambda p: "purchase" if p == "" else "cancellation" if p == "C" else "other")


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Apply the cleaning steps in order.

    Input: normalised frame. Output: (purchases, cancellations, log dict).
    """
    log: dict = {"steps": []}

    def step(name: str, before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
        log["steps"].append(
            {"step": name, "rows_before": len(before), "rows_after": len(after),
             "removed": len(before) - len(after)}
        )
        return after

    df = step("drop_sheet_overlap", df, drop_sheet_overlap(df))
    df = df.assign(kind=invoice_type(df.invoice))
    df = step("drop_invoice_prefix_other_than_C", df, df.loc[df.kind != "other"])
    df = step("drop_missing_description", df, df.loc[df.description.notna()])
    codes = non_product_codes()
    df = step("drop_non_product_codes", df, df.loc[~df.stock_code.isin(codes)])
    # Stock adjustments: no customer and price <= 0 (descriptions such as 'check', 'damaged').
    adj = df.customer_id.isna() & (df.price <= 0)
    df = step("drop_stock_adjustments_price_le0_no_customer", df, df.loc[~adj])

    is_purchase = (df.kind == "purchase") & (df.quantity > 0)
    is_cancel = df.kind == "cancellation"
    rest = df.loc[~is_purchase & ~is_cancel]
    log["rows_neither_purchase_nor_cancellation"] = len(rest)
    log["cancellation_rows_with_positive_quantity"] = int((is_cancel & (df.quantity > 0)).sum())

    cols = ["invoice", "stock_code", "description", "quantity", "invoice_date", "price",
            "customer_id", "country"]
    purchases = df.loc[is_purchase, cols].reset_index(drop=True)
    cancels = df.loc[is_cancel & (df.quantity < 0), cols].reset_index(drop=True)
    log["purchases"] = {
        "rows": len(purchases),
        "invoices": purchases.invoice.nunique(),
        "rows_with_customer": int(purchases.customer_id.notna().sum()),
        "invoices_with_customer": purchases.loc[purchases.customer_id.notna()].invoice.nunique(),
        "rows_without_customer": int(purchases.customer_id.isna().sum()),
        "invoices_without_customer": purchases.loc[purchases.customer_id.isna()].invoice.nunique(),
        "invoices_mixed_customer_and_missing": int(
            purchases.groupby("invoice").customer_id.apply(lambda s: s.isna().any() and s.notna().any()).sum()
        ),
    }
    log["cancellations"] = {
        "rows": len(cancels),
        "invoices": cancels.invoice.nunique(),
        "rows_with_customer": int(cancels.customer_id.notna().sum()),
        "rows_without_customer": int(cancels.customer_id.isna().sum()),
    }
    log["exact_duplicate_purchase_rows_kept"] = int(purchases.duplicated().sum())
    return purchases, cancels, log


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean, write data/processed/{purchases,cancellations}.parquet and the log."""
    purchases, cancels, log = clean(load())
    PROCESSED.mkdir(parents=True, exist_ok=True)
    purchases.to_parquet(PROCESSED / "purchases.parquet", index=False)
    cancels.to_parquet(PROCESSED / "cancellations.parquet", index=False)
    write_log("03_clean", log)
    return purchases, cancels


if __name__ == "__main__":
    run()
    import json

    from rafim.paths import LOGS
    print(json.dumps(json.loads((LOGS / "03_clean.json").read_text()), indent=1))
