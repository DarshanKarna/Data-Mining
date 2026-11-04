"""Load Online Retail II from the raw .xlsx once and cache it as Parquet.

All column-name mapping lives here. The real file (checked 2026-10-29) has two
sheets, 'Year 2009-2010' and 'Year 2010-2011', each with the columns
Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from rafim.paths import INTERIM, RAW, write_log

RAW_FILE = RAW / "online_retail_II.xlsx"
PARQUET_FILE = INTERIM / "online_retail_ii.parquet"

# Raw column name -> canonical name used in the code.
COLUMN_MAP = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}
TEXT_COLUMNS = ["Invoice", "StockCode", "Description", "Customer ID", "Country"]


def _sha256(path) -> str:
    """Return the hex SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_raw_excel() -> pd.DataFrame:
    """Read every sheet of the raw workbook into one frame.

    Output: frame with canonical column names plus 'sheet' and 'sheet_row'
    (0-based data row within its sheet), text columns kept as strings.
    """
    sheets = pd.read_excel(RAW_FILE, sheet_name=None, dtype={c: str for c in TEXT_COLUMNS})
    frames = []
    for name, df in sheets.items():
        missing = set(COLUMN_MAP) - set(df.columns)
        if missing:
            raise ValueError(f"sheet {name!r} lacks columns {sorted(missing)}")
        df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
        df["sheet"] = name
        df["sheet_row"] = range(len(df))
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise types: strip/upper-case codes, parse dates, numeric quantity and price.

    Input: frame from read_raw_excel. Output: new frame with normalised columns.
    """
    out = df.copy()
    out["invoice"] = out["invoice"].str.strip().str.upper()
    out["stock_code"] = out["stock_code"].str.strip().str.upper()
    out["description"] = out["description"].str.strip()
    out["customer_id"] = out["customer_id"].str.strip().str.replace(r"\.0$", "", regex=True)
    out["country"] = out["country"].str.strip()
    out["invoice_date"] = pd.to_datetime(out["invoice_date"])
    out["quantity"] = pd.to_numeric(out["quantity"]).astype("int64")
    out["price"] = pd.to_numeric(out["price"]).astype("float64")
    return out


def build_parquet(force: bool = False) -> pd.DataFrame:
    """Convert the raw workbook to Parquet once and log what was read.

    Output: the normalised frame (also written to data/interim/).
    """
    if PARQUET_FILE.exists() and not force:
        return pd.read_parquet(PARQUET_FILE)
    raw = read_raw_excel()
    df = normalize(raw)
    INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PARQUET_FILE, index=False)
    write_log(
        "01_load",
        {
            "raw_file": RAW_FILE.name,
            "raw_sha256": _sha256(RAW_FILE),
            "sheets": {k: int(v) for k, v in df.groupby("sheet").size().items()},
            "rows_total": len(df),
            "raw_columns": list(COLUMN_MAP),
            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        },
    )
    return df


def load() -> pd.DataFrame:
    """Return the normalised dataset, reading the Parquet cache."""
    return build_parquet(force=False)


if __name__ == "__main__":
    frame = build_parquet(force=True)
    print(frame.shape)
    print(frame.dtypes)
