# Decisions log

Every decision that is not fixed by CLAUDE.md, or that deviates from it or from the
proposal, is recorded here with date and reason. Counts quoted come from `results/logs/`.

## 2026-10-29 Data loading

- **Two sheets, overlapping dates.** The workbook has sheets `Year 2009-2010`
  (525,461 rows, 2009-12-01 to 2010-12-09) and `Year 2010-2011` (541,910 rows,
  2010-12-01 to 2011-12-09). 1,088 invoices (22,523 rows) dated 2010-12-01 to 2010-12-09
  appear in both sheets. Their rows are identical as multisets in both sheets
  (`scripts/inspect_data.py`). Decision: drop the copy in `Year 2009-2010`.
  Without this, those baskets would be counted twice. UCI's figure of 1,067,371 rows
  includes the duplicated block.
- **Column names.** The file uses `Invoice, StockCode, Description, Quantity, InvoiceDate,
  Price, Customer ID, Country`, not the UCI variable names. Mapped once in
  `src/rafim/load.py`. Invoice, StockCode and Customer ID are read as text because they
  mix integers and strings in the file.

## 2026-10-29 Cleaning

- **Invoice prefixes.** Seen: digits only, `C`, and `A` (6 rows, all `Adjust bad debt`
  with stock code `B` and negative price, no customer). Decision: drop prefix `A` rows.
  They are accounting entries, not sales or returns.
- **Non-product codes.** 61 stock codes do not match the product pattern
  `5 digits + up to 2 letters`. 25 of them are fees, postage, manual adjustments, tests,
  bad debt or gift vouchers and are listed with evidence in
  `configs/non_product_codes.yaml`. The other codes outside the pattern (`DCGS*`,
  `SP1002`, `PADS`) have product descriptions and are kept.
- **Stock adjustments.** Rows with no Customer ID and price <= 0 are dropped. Evidence:
  all 3,457 non-C rows with negative quantity have price 0 and no customer, with
  descriptions such as `check`, `damaged`, `missing`, `thrown away`. Positive-quantity
  rows of this kind carry notes such as `found` and `adjustment`. Zero-price rows that do
  have a customer (71 purchase rows with product descriptions) are kept.
- **Exact duplicate lines within one invoice** (11,731 purchase rows after cleaning) are
  kept. Nothing in the data shows they are entry errors. They do not change basket
  membership. For linking, quantities per (invoice, stock code) are summed, so a
  duplicate line raises the purchased quantity.

## 2026-10-29 Return linking

- Implemented as CLAUDE.md section 4.5. Additional choices:
  - A purchase item is one (invoice, stock code) pair with summed quantity.
  - "Dated before" is strict: a purchase with the same timestamp as the cancellation is
    not a candidate.
  - Cancellations are processed in date order. Capacity used by an earlier cancellation is
    not available to a later one, so one purchase is never returned twice.
  - A cancellation whose quantity exceeds all earlier matching purchases is
    `partially_linked`. Its allocated part counts, the rest is logged as unallocated.
- Deviation from the proposal: the proposal (Data preprocessing, step 3) links each
  cancellation to the single most recent earlier purchase. CLAUDE.md walks back over
  several purchases until the quantity is used up and adds the partial-return policy.
  We follow CLAUDE.md. Reason: a cancellation can exceed the quantity of the most recent
  purchase (249 cancellation lines were split across more than one purchase), and the
  single-purchase rule cannot express a partial return. The report states this.

## 2026-10-29 Mining set-up

- **Frequency test.** An itemset is frequent when count / n >= minsup, the same test
  mlxtend applies, so outputs can be compared exactly.
- **Minimum support grid**: 0.04, 0.03, 0.02, 0.015, 0.01, 0.0075, 0.005, 0.004, 0.003
  (fractions of train baskets, n = 18,192). Reasoning from item frequencies in train:
  only 1 item has sup >= 0.10 and 23 items have sup >= 0.05, so 0.05 yields singletons
  only. At 0.03 there are 96 standard itemsets, at 0.003 there are 11,379 with up to 7
  items. Our Apriori took about 13 s at 0.003 on this machine in a probe run. Time budget:
  60 s per single mining run. 0.0025 gave 18,049 itemsets with up to 9 items, and rule
  generation grows with 2^k per itemset, so the grid stops at 0.003.
- **Main operating point** for E3 to E6 tables: minsup 0.005 (3,709 retained itemsets in
  the probe). It is the lowest grid value at which itemsets of length 4 and 5 appear while
  rule counts stay readable. E3 is also reported across the whole grid.
- **Minimum confidence** 0.5 for both measures (conf for baseline, rconf for
  return-aware). CLAUDE.md does not fix it. 0.5 means the consequent appears in at least
  half of the baskets that contain the antecedent.
- **Lift** is computed under the run's measure: baseline lift = conf / sup(B),
  return-aware lift = rconf / rsup(B).
- **Rule ranking** for top-k: by confidence under the measure, then lift, then support,
  then rule text (deterministic tie break).
- **Apriori counting** uses vertical tid bitsets (uint64 words, popcount), as CLAUDE.md
  section 5 prescribes. Candidate generation and subset pruning follow Agrawal and
  Srikant. In retained mode both counts come from the same pass.
- **High return rate (E4).** "High" means rr(X) >= 2 x the train line return rate (share of
  train basket items marked returned under the default policy, 0.00832), so the threshold is
  0.01664. A factor of 2 marks itemsets whose returns are at least double the typical item.
- **Hold-out censoring check (E5).** 90% of linked returns happen within 90 days of purchase
  (`results/logs/04_link_returns.json`), so purchases in the last 90 days of the data have had
  less time to be returned. E5 is also reported on a censored hold-out that keeps only baskets
  dated on or before 2011-09-10 (data end minus 90 days).
- **Peak memory** is measured with tracemalloc (Python and NumPy allocations) in a separate,
  untimed run, because tracemalloc slows Python code. It is not process RSS.

## 2026-10-30 Analyses added after the first full run

- **Apriori memory fix.** The first full run showed a tracemalloc peak of 1,043 MiB for
  retained Apriori at minsup 0.005: surviving itemsets held views into whole candidate blocks.
  The code now copies only surviving rows (13 MiB at the same setting). The run was stopped
  and repeated. Only results of the repeated run are reported.
- **E5b, rules on which the runs disagree.** At the main minsup the top-50 rule lists of both
  runs are identical, so the top-k test in E5 cannot separate them. E5b evaluates on hold-out
  the three groups: rules in both runs, baseline-only rules and return-aware-only rules, under
  both partial-return policies. This extends E5 and does not change any default.
- **E4b, persistence of rr.** Checks whether rr on train predicts rr on hold-out for baseline
  itemsets of size >= 2, using Spearman correlation and a one-sided Mann-Whitney U test
  (flagged vs not flagged). Itemsets need at least 30 hold-out baskets (`min_holdout_count`)
  so that hold-out rr is not computed from a handful of baskets.

## Deviations from the proposal (to state in the report)

1. Return linking walks back over several purchases and adds a partial-return policy (see
   Return linking above).
2. The proposal's first experiment runs the algorithms "after the usual cleaning step that
   discards cancelled invoices". We do the same for the baseline. Both runs are restricted to
   baskets with a Customer ID so that they use the same baskets (CLAUDE.md section 4.4),
   which the proposal did not state.
3. E4b and E5b are added analyses, not in the proposal's evaluation table.

- **FP-Growth** includes the single-path shortcut of Han et al. (all combinations of a
  single-path tree are emitted directly).
