# Return-Aware Support for Apriori and FP-Growth on Online Retail Transactions

Course project, COSC-3026-F01 Data Mining and Data Warehousing.

Standard support counts an item in a basket even when the customer later returned it.
This code links each cancellation in Online Retail II to the purchase it reverses, builds the
kept basket k(t) of every purchase basket t, and mines with **retained support**
rsup(X) = |{t : X ⊆ k(t)}| / |D| next to standard support. Retained support is
anti-monotone, so Apriori and FP-Growth prune on it unchanged.

## Setup

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Windows
.venv\Scripts\python -m pip install -e .
```

Download the dataset (UCI id 502, CC BY 4.0) to `data/raw/online_retail_II.xlsx`:
https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip

## Run

```
python -m rafim.run --config configs/default.yaml   # pipeline + experiments E1-E7
python -m rafim.figures                              # figures from results/tables/
python report/build_docx.py                          # report.docx + page count
pytest                                               # correctness gates
```

The first run converts the workbook to Parquet (about 2 minutes). The full run takes about
15 to 20 minutes on a 16-thread laptop, most of it in the timed benchmark.

## Layout

| Path | Content |
| --- | --- |
| `src/rafim/load.py` | read both sheets, column mapping, Parquet cache |
| `src/rafim/clean.py` | sheet overlap, non-product codes, stock adjustments, purchase/cancellation split |
| `src/rafim/link_returns.py` | return linking and partial-return policies |
| `src/rafim/baskets.py` | full and kept baskets as sparse matrices, time split |
| `src/rafim/measures.py` | tid bitsets, sup, rsup, rr |
| `src/rafim/apriori.py`, `fpgrowth.py` | both miners with `measure = standard / retained` |
| `src/rafim/rules.py` | rules with conf, rconf, lift, rr |
| `src/rafim/evaluate.py`, `bench.py`, `run.py` | experiments E1-E7 |
| `configs/` | run config and the non-product code list with evidence |
| `docs/decisions.md` | every decision with its reason |
| `results/logs`, `results/tables`, `results/figures` | outputs used in the report |
| `tests/` | linking cases, agreement with mlxtend, property tests |
