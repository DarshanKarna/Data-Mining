# Return-Aware Support for Apriori and FP-Growth on Online Retail Transactions

Course project for COSC-3026-F01 Data Mining and Data Warehousing.

## Overview

Standard support counts an item in a basket even when the customer later returned it.
Online Retail II stores cancellations as separate invoices whose number starts with `C`.
This code links each cancellation line to the purchase it reverses, builds the kept basket
k(t) of every purchase basket t, and mines with **retained support** next to standard
support. Retained support is anti-monotone, so Apriori and FP-Growth prune on it unchanged.

We implement both algorithms ourselves, each with a `measure` switch (`standard` or
`retained`), and run two experiment families on the same data:

1. Baseline: both algorithms with standard support.
2. Return-aware: both algorithms with retained support.

### Definitions

| Symbol | Meaning |
| --- | --- |
| `sup(X)` | share of baskets t with X ⊆ t (standard support) |
| `rsup(X)` | share of baskets t with X ⊆ k(t) (retained support) |
| `rr(X)` | itemset return rate, `1 - rsup(X) / sup(X)` |
| `conf(A ⇒ B)` | `sup(A ∪ B) / sup(A)` (standard confidence) |
| `rconf(A ⇒ B)` | `rsup(A ∪ B) / rsup(A)` (retained confidence) |

Anti-monotonicity: if X ⊆ Y and Y ⊆ k(t), then X ⊆ k(t), so rsup(Y) ≤ rsup(X).

Terms used throughout the code and report: baseline, return-aware, kept basket,
linked return, unlinked cancellation.

## Dataset

Online Retail II, UCI Machine Learning Repository (id 502, DOI 10.24432/C5CG6D,
CC BY 4.0, creator Daqing Chen). A UK online giftware retailer, transactions from
2009-12-01 to 2011-12-09.

The data is not stored in the repo (`data/` is gitignored). Download
https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip and place the workbook
at `data/raw/online_retail_II.xlsx`.

Key figures after cleaning (from `results/tables/dataset_summary.csv`):

| Quantity | Value |
| --- | --- |
| Raw rows (both sheets) | 1,067,371 |
| Rows after removing the duplicated sheet block | 1,044,848 |
| Purchase invoices used as baskets (with Customer ID) | 36,597 |
| Customers | 5,853 |
| Items (stock codes) in baskets | 4,621 |
| Cancellation lines | 17,974 |
| Linked / partially linked / unlinked | 15,933 / 117 / 1,924 |
| Mean basket size | 20.93 |
| Line return rate | 0.77% |

The workbook has two sheets whose dates overlap (2010-12-01 to 2010-12-09). The copy in
the first sheet is dropped so those baskets are not counted twice. See `docs/decisions.md`.

## Method

Pipeline steps, each logging counts to `results/logs/`:

1. **Load** both sheets, map column names in one place, cache as Parquet.
2. **Clean** by dropping rows with no description, non-product codes
   (`configs/non_product_codes.yaml`), `A` prefix accounting rows and stock adjustments.
3. **Split** rows into purchases and cancellations.
4. **Customer scope** default is rows with a Customer ID. Sensitivity run adds anonymous
   purchases with k(t) = t.
5. **Link returns.** Each cancellation line (customer, stock code, date, quantity) is
   allocated to earlier purchase lines of the same customer and stock code, most recent
   first, until the quantity is used up. Linking runs on the full data before any time
   split.
6. **Returned item rule.** Default `partial_return_policy: full` marks an item returned
   only when the cancelled quantity covers the full purchased quantity. `any` marks it
   returned on any allocation.
7. **Baskets** as sparse matrices, one per purchase invoice. k(t) holds the items not
   marked returned.
8. **Time split.** Train is 2009-12-01 to 2010-11-30, hold-out is 2010-12-01 onwards.

### Algorithms

- `apriori.py`: level-wise candidate generation with subset pruning and tid-set bitset
  counting. In retained mode it keeps two counts per candidate in one pass and prunes on
  the retained count.
- `fpgrowth.py`: two scans, FP-tree, conditional pattern bases. In retained mode the tree
  is built from kept baskets. Standard support of each output itemset is computed
  afterwards from tid bitsets, so rr(X) needs no second tree.
- `rules.py`: rule generation with conf, rconf, lift and rr.
- mlxtend (`apriori`, `fpgrowth`) is used only to check our standard mode and as a
  runtime reference.

## Experiments

| ID | What it measures |
| --- | --- |
| E1 | Baseline runtime, peak memory, itemset and rule counts per minimum support |
| E2 | Same for return-aware, plus the cost of the extra counter |
| E3 | Itemsets and rules that appear or disappear, top-k overlap, Kendall tau |
| E4 | Distribution of rr(X) and rules with a high return rate |
| E5 | Hold-out stability of top-k train rules |
| E6 | Sensitivity: `full` vs `any` policy, with vs without anonymous purchases |
| E7 | Apriori and FP-Growth agreement under each measure |

Settings are in `configs/default.yaml` (minimum support grid 0.04 to 0.003, main value
0.005, minimum confidence 0.5, three timing repeats).

## Results summary

All numbers come from `results/tables/`. They describe this dataset and this machine only.

- **E7 agreement.** Apriori and FP-Growth return identical itemsets at all nine minimum
  support values under both measures.
- **E3 output change.** At minsup 0.005, standard support gives 3,761 itemsets and
  retained support gives 3,709. 52 itemsets drop out and none appear. Rules go from
  2,638 to 2,588. Top-10, top-20 and top-50 overlap is 1.0, and Kendall tau on common
  rules is 0.983.
- **E2 cost.** Retained mode costs about 1.8x to 2.3x the runtime of standard mode for
  our Apriori, because of the second counter. For our FP-Growth the ratio is about 1.0.
- **E4 return rates.** Train line return rate is 0.83%. With the threshold at twice that
  rate, 426 of 3,761 itemsets have a high rr(X), and 174 of 2,638 baseline rules (6.6%)
  sit on a high-rr itemset.
- **E5 hold-out.** All top-k rules from both runs still meet minimum confidence on the
  hold-out. Mean confidence change is about -0.03 (k = 10) to -0.06 (k = 50) for both,
  so the two rankings behave almost the same there.
- **E6 sensitivity.** The `any` policy raises the line return rate to 2.2% and removes
  270 itemsets at minsup 0.005 instead of 52.

Retained support changes the mined output only slightly at a 0.8% line return rate. The
largest effect is on rules whose items are often returned.

## Setup

Python 3.11 or newer.

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Windows
.venv\Scripts\python -m pip install -e .
```

On macOS or Linux use `.venv/bin/python` in place of `.venv\Scripts\python`.

## Run

```
python -m rafim.run --config configs/default.yaml   # pipeline + experiments E1-E7
python -m rafim.figures                              # figures from results/tables/
python report/build_docx.py                          # report.docx + page count
pytest                                               # correctness gates
ruff check .                                         # lint
```

The first run converts the workbook to Parquet (about 2 minutes). The full run takes about
15 to 20 minutes on a 16-thread laptop, most of it in the timed benchmark. Every run
writes its config, git commit hash, library versions, machine info and timestamp to
`results/runs/<run_id>/`. Do not compare runtimes across machines.

## Tests

The tests in `tests/` are the correctness gates for the experiments:

- Our Apriori, our FP-Growth and mlxtend agree in standard mode, on toy data and on a
  sample of the real data.
- With no returns (k(t) = t), retained mode equals standard mode.
- Our Apriori and FP-Growth agree in retained mode.
- Hypothesis property test: rsup is anti-monotone and rsup(X) ≤ sup(X).
- Linking cases: multiple purchases, partial returns, cancellation before any purchase,
  missing customer, return larger than any single purchase line.

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
| `src/rafim/figures.py` | regenerates figures from `results/tables/` |
| `configs/` | run config and the non-product code list with evidence |
| `docs/` | `proposal.tex` and `decisions.md` (every decision with its reason) |
| `results/logs`, `results/tables`, `results/figures` | outputs used in the report |
| `report/` | `draft.md`, `references.md`, `build_docx.py`, built report |
| `presentation/outline.md` | 5-minute presentation outline |
| `submission/code.zip` | packaged code for Brightspace |
| `tests/` | linking cases, agreement with mlxtend, property tests |

## Limitations

- Return linking needs a Customer ID, so anonymous cancellations stay unlinked
  (1,924 of 17,974 cancellation lines are unlinked).
- Purchases near the end of the data have little time to be returned, so the hold-out has
  a censoring effect. E5 reports a censored hold-out variant for this.
- The link between a cancellation and a purchase is inferred by the allocation rule, not
  recorded in the data.
- Results come from one retailer and one machine.

## References

The main sources are Agrawal and Srikant (VLDB 1994), Han, Pei and Yin (SIGMOD 2000),
Chen (UCI, 2012) and Raschka (MLxtend, JOSS 2018). The verified list is in
`report/references.md`.

## Authors

Group of 2. Names and contribution percentages are in the report title block.
