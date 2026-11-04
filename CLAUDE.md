# CLAUDE.md

Course project for COSC-3026-F01 Data Mining and Data Warehousing.
Title: Return-Aware Support for Apriori and FP-Growth on Online Retail Transactions.
Group of 2 (names go in the report title block, with contribution percentages).

The approved proposal is in `docs/proposal.tex`. The final report must stay consistent with it. If the work deviates from the proposal, record the deviation and the reason in `docs/decisions.md` and mention it in the report.

## 1. What the assignment requires

The brief asks for two algorithms from one family plus one small, original addition, then two experiments on the same dataset:

1. Both algorithms as published, tested on the dataset, with results.
2. Both algorithms with our addition, same dataset, with results.

Deliverables and deadlines:

| Item | Weight | Due | Format |
| --- | --- | --- | --- |
| P1 Proposal | 5% | 30 Oct 2026 | Word, max 3 pages (done, see `docs/proposal.tex`) |
| Final report | 15% | 29 Nov 2026 | Word, IEEE two-column, 10 pt, max 10 pages, plus code as a separate file |
| Presentation | 10% | Brief says 31 March, which conflicts with the term. Confirm with the instructor | 5 minutes, every member must present or gets zero |

Submit everything on Brightspace. Email submissions are rejected. Late penalty is 10% per day including weekends, and anything more than 3 days late scores zero.

Final report sections and weights (structure the report exactly in this order):

1. Title block: title, group name, members, contribution percentage per member.
2. Abstract (5%): revised from the proposal, must include actual results with numbers.
3. Introduction and Motivation (5%): purpose, aim, objectives, uniqueness of the work, with sub-headings. Summarize everything done.
4. Literature / Background Study (5%): for each paper, its significant work and its limitation, clearly separated from our contribution. Last paragraph summarizes our analysis of prior work. Use journal and conference papers, preferably from ACM Computing Surveys, Data and Knowledge Engineering, VLDB, ACM SIGKDD, ICDE, IEEE ICDM.
5. Proposed Model (5%): explain both algorithms and our change, with a workflow diagram.
6. Results (30%): the largest section. Dataset information first, then the mining concepts implemented, tables, charts, baseline vs return-aware comparison.
7. Limitations and Challenges (15%): settings where the approach performs poorly, why, and the challenges we faced.
8. Conclusions and Future Work (15%): key findings, larger implications, significance, what we would do with more time.
9. References (10%): IEEE format, mostly 2020 to 2025.

## 2. The project in one paragraph

Standard support counts every item in a basket at checkout, so items the customer later returned still count. Online Retail II stores cancellations as separate invoices whose number starts with C. We link each cancellation line to the purchase it reverses, define the kept view k(t) of each basket, and replace support with retained support, the fraction of baskets in which every item of an itemset was bought and kept. Retained support is anti-monotone, so Apriori and FP-Growth keep their pruning unchanged.

Definitions (use these names everywhere, in code and in the report):

- `sup(X) = |{t in D : X ⊆ t}| / |D|` standard support
- `rsup(X) = |{t in D : X ⊆ k(t)}| / |D|` retained support
- `rr(X) = 1 - rsup(X) / sup(X)` itemset return rate
- `conf(A ⇒ B) = sup(A ∪ B) / sup(A)` standard confidence
- `rconf(A ⇒ B) = rsup(A ∪ B) / rsup(A)` retained confidence
- Proof of anti-monotonicity: if X ⊆ Y and Y ⊆ k(t), then X ⊆ k(t), so rsup(Y) ≤ rsup(X).

Terminology is fixed: "baseline" (standard support), "return-aware" (retained support), "kept basket", "linked return", "unlinked cancellation". Do not alternate synonyms.

## 3. Dataset

- Online Retail II, UCI Machine Learning Repository, id 502, DOI 10.24432/C5CG6D, CC BY 4.0. Creator: Daqing Chen.
- UCI page: https://archive.ics.uci.edu/dataset/502/online+retail+ii
- Download: https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip (one .xlsx, 43.5 MB). Alternative: `ucimlrepo.fetch_ucirepo(id=502)`.
- Per UCI: 1,067,371 rows, UK-based non-store online retailer, transactions 01/12/2009 to 09/12/2011, mainly all-occasion giftware, many customers are wholesalers, has missing values. Invoice numbers starting with "c"/"C" indicate a cancellation.
- The UCI variable list uses old names (InvoiceNo, UnitPrice, CustomerID). The actual file may use different column names and may split the years across sheets. Inspect the real file, log sheet names, column names, dtypes and row counts, and map them in one place (`src/rafim/load.py`). Never assume.
- Reading the .xlsx is slow. Convert once to Parquet in `data/interim/` and read Parquet afterwards.
- `data/` is gitignored. Never commit the raw data.

## 4. Pipeline and default decisions

Each step writes its output to `data/processed/` and a short log (counts before and after) to `results/logs/`. Every number that appears in the report must come from these logs or from `results/tables/`.

1. Load and normalize: strip and upper-case StockCode, parse dates, keep Description only as a label.
2. Inspect and clean: drop rows with no description. List stock codes that are not products (postage, fees, manual adjustments and similar) by inspecting codes and descriptions, save the list to `configs/non_product_codes.yaml` with the evidence, and drop them. Log any invoice prefixes other than C and decide how to treat them in `docs/decisions.md`.
3. Split rows into purchases (non-C invoice, Quantity > 0) and cancellations (C invoice).
4. Customer scope. Default: restrict both experiments to rows with a Customer ID, because returns of anonymous rows cannot be linked and the comparison must use the same baskets. Report how many rows and invoices this removes. Sensitivity run: include anonymous purchases with k(t) = t.
5. Link returns (`src/rafim/link_returns.py`). For each cancellation line (customer c, stock s, date d, quantity q), allocate |q| to purchase lines of the same customer and stock code dated before d, starting from the most recent and walking backwards until the quantity is used up. Record every allocation. A cancellation with no Customer ID or no earlier matching purchase is "unlinked", logged with its reason. Link on the full dataset before any time split. Report the distribution of lag between purchase and cancellation.
6. Returned item rule. Default `partial_return_policy: full`, an item counts as returned in a basket only when the allocated cancelled quantity covers the full purchased quantity. Sensitivity: `any`, where any allocated cancellation marks the item returned. Report both.
7. Baskets: one basket per purchase invoice, items = set of stock codes. k(t) = items not marked returned. Store as sparse matrices or bitsets, never as a dense DataFrame of the full item set.
8. Time split: train = invoices dated 2009-12-01 to 2010-11-30, hold-out = 2010-12-01 onwards. Mining runs on train, rule stability is checked on hold-out.

## 5. Algorithms

Implement both algorithms ourselves in `src/rafim/`, each with a `measure` switch (`standard` or `retained`):

- `apriori.py`: level-wise candidate generation with subset pruning. Count candidates with bitset or vertical tid-set intersection. In retained mode, keep two counts per candidate in the same pass (full basket and kept basket) and prune on the retained count.
- `fpgrowth.py`: two scans, FP-tree, conditional pattern bases, no candidate generation. In retained mode, build the tree from kept baskets so node counts are retained counts. Compute standard support of each output itemset afterwards from tid bitsets of the full baskets, so rr(X) needs no second tree.
- `rules.py`: rule generation from frequent itemsets with conf, rconf, lift, and rr.
- Baseline reference: `mlxtend.frequent_patterns.apriori` and `fpgrowth` (Raschka 2018). Use them only to check correctness of our standard mode and as an extra runtime reference.

Correctness gates (tests in `tests/`, all must pass before any experiment is reported):

- Our Apriori, our FP-Growth and mlxtend give identical itemsets and supports in standard mode on toy data and on a sample of the real data.
- With no returns (k(t) = t for all t), retained mode output equals standard mode output.
- Our Apriori and our FP-Growth give identical output in retained mode.
- Property test (hypothesis): rsup is anti-monotone and rsup(X) ≤ sup(X) on random baskets.
- Linking tests on hand-built cases: multiple purchases, partial returns, cancellation before any purchase, missing customer, return larger than any single purchase line.

## 6. Experiments

Configs live in `configs/*.yaml`. One command runs everything: `python -m rafim.run --config configs/default.yaml`. Every run writes the config, git commit hash, Python and library versions, machine info and timestamp to `results/runs/<run_id>/`.

Minimum support grid: choose after inspecting item frequencies so that the smallest value still lets Apriori finish within a stated time budget and the grid spans from a few dozen to many thousands of itemsets. Record the reasoning in `docs/decisions.md`.

| Experiment | What to measure |
| --- | --- |
| E1 Baseline: both algorithms, standard support | runtime, peak memory, number of itemsets and rules per min support |
| E2 Return-aware: both algorithms, retained support | same measures, plus cost of the extra counter vs E1 |
| E3 Output change | itemsets and rules that appear or disappear, top-k overlap (k = 10, 20, 50), Kendall rank correlation of rule rankings |
| E4 Return rates | distribution of rr(X), list of rules whose itemset return rate is high. Define "high" relative to the dataset-wide line return rate and state the threshold |
| E5 Hold-out stability | for top-k train rules from E1 and from E2, compute rconf on hold-out kept baskets and report the share that still meets min confidence, and the mean change in confidence |
| E6 Sensitivity | partial_return_policy full vs any, with vs without anonymous purchases |
| E7 Algorithm agreement | Apriori and FP-Growth give identical itemsets under each measure |

Timing: `time.perf_counter`, at least 3 repeats, report median and spread. Memory: peak RSS via psutil or tracemalloc, state which one. Do not compare runtimes across different machines.

Do not claim "significant" without a statistical test. Report effect sizes with numbers.

## 7. Figures and tables for the report

Save every figure as PDF and 300 dpi PNG in `results/figures/`, sized for one IEEE column (3.5 in wide) unless it must span both. Each figure has a script that regenerates it from `results/tables/`.

Minimum set:

1. Workflow diagram of the full pipeline (load, clean, link returns, baskets and kept baskets, Apriori / FP-Growth in both modes, rules, evaluation). Keep its source (graphviz or matplotlib) in the repo.
2. Dataset summary table: rows, invoices, customers, items, cancellation lines, linked and unlinked counts, date range, basket size statistics.
3. Runtime vs minimum support, both algorithms, both measures.
4. Number of frequent itemsets vs minimum support, both measures.
5. Distribution of itemset return rate rr(X).
6. Top rules table under baseline vs return-aware, with sup, rsup, conf, rconf, lift, rr, and product descriptions.
7. Hold-out stability chart, baseline rules vs return-aware rules.
8. Sensitivity table (E6).

## 8. Report production

- Draft the report in `report/draft.md`, one section at a time, in the order of section 1 above.
- Build `report/report.docx` with python-docx: title block in one column, body in two columns, Times New Roman 10 pt, IEEE-style headings, figures 3.5 in wide, references in IEEE style. Check the page count (convert with LibreOffice to PDF if it is available) and keep it at or under 10 pages.
- `report/references.md` holds the reference list. Citations in text use [n] in order of first appearance.
- Package the code for submission as `submission/code.zip` (src, configs, scripts, tests, README, requirements, no data).

## 9. Verified references (use these, in IEEE style)

Every entry below was checked against a publisher, DOI, dblp, or institutional page.

1. R. Agrawal and R. Srikant, "Fast algorithms for mining association rules in large databases," Proc. 20th VLDB, Santiago, Chile, 1994, pp. 487-499.
2. J. Han, J. Pei, and Y. Yin, "Mining frequent patterns without candidate generation," Proc. ACM SIGMOD, Dallas, TX, 2000, pp. 1-12, doi: 10.1145/335191.335372.
3. D. Chen, "Online Retail II," UCI Machine Learning Repository, 2012, doi: 10.24432/C5CG6D.
4. shahashmi, "market-basket-analysis," GitHub, https://github.com/shahashmi/market-basket-analysis (example that removes returns and cancellations, keeping 396,470 of 541,909 rows of the one-year release, then runs Apriori).
5. D. Karl, "Forecasting e-commerce consumer returns: A systematic literature review," Manage. Rev. Quart., vol. 75, no. 3, pp. 1-56, 2025, doi: 10.1007/s11301-024-00436-x. (Reports, citing NRF/Appriss Retail, $212 billion of online merchandise returned in the US in 2022, 16.5% of online sales.)
6. Q. H. Duong et al., "Understanding product returns: A systematic literature review using machine learning and bibliometric analysis," Int. J. Prod. Econ., vol. 243, Art. no. 108340, 2022, doi: 10.1016/j.ijpe.2021.108340.
7. J. Li, J. He, and Y. Zhu, "E-tail product return prediction via hypergraph-based local graph cut," Proc. 24th ACM SIGKDD, 2018, pp. 519-527, doi: 10.1145/3219819.3219829.
8. G. Shang, E. C. McKie, M. E. Ferguson, and M. R. Galbreth, "Using transactions data to improve consumer returns forecasting," J. Oper. Manage., vol. 66, no. 3, pp. 326-348, 2020, doi: 10.1002/joom.1071.
9. P. Ambilkar, V. Dohale, A. Gunasekaran, and V. Bilolikar, "Product returns management: A comprehensive review and future research agenda," Int. J. Prod. Res., vol. 60, no. 12, pp. 3920-3944, 2022, doi: 10.1080/00207543.2021.1933645.
10. W. Gan et al., "A survey of utility-oriented pattern mining," IEEE Trans. Knowl. Data Eng., vol. 33, no. 4, pp. 1306-1327, 2021, doi: 10.1109/TKDE.2019.2942594. (States utility is neither monotone nor anti-monotone.)
11. K. Meißner, A. B. Stevenson, and J. Rieck, "Identifying non-intuitive relationships within returns data of a furniture online-shop using temporal data mining," ACIIDS 2022, CCIS vol. 1716, Springer, 2022, pp. 299-312, doi: 10.1007/978-981-19-8234-7_24. (Closest related work. Mines the return records themselves, not purchase baskets.)
12. D. Chen, S. L. Sain, and K. Guo, "Data mining for the online retail industry: A case study of RFM model-based customer segmentation using data mining," J. Database Marketing Customer Strategy Manage., vol. 19, no. 3, pp. 197-208, 2012, doi: 10.1057/dbm.2012.17.
13. S. Raschka, "MLxtend," J. Open Source Softw., vol. 3, no. 24, Art. no. 638, 2018, doi: 10.21105/joss.00638.
14. L. Bustio-Martínez et al., "FPGA/GPU-based acceleration for frequent itemsets mining: A comprehensive review," ACM Comput. Surv., vol. 54, no. 9, 2022, doi: 10.1145/3472289.

The literature review needs more papers, mostly 2020 to 2025, from the venues in section 1. Before adding any reference: open the actual page (publisher, DOI resolver, dblp, ACM DL, IEEE Xplore), confirm authors, title, venue, year, pages and DOI, and record the URL you checked in `report/references.md`. Never cite a paper you have not opened. Never cite from memory. If a claim cannot be sourced, cut it.

## 10. Rules for working in this repo

- Never invent numbers, results, citations, quotes or dataset facts. If something is unknown, say so and find out.
- Report only what the code produced. If a result is disappointing or contradicts the hypothesis, report it as it is and discuss it.
- Ask before changing any default decision in section 4 or section 6. Record every decision in `docs/decisions.md` with date and reason.
- Keep functions small and typed, with docstrings that state inputs and outputs. Run `pytest` and `ruff` before calling a phase done.
- Use fixed random seeds for any sampling.
- Keep raw data read-only. All derived data is reproducible from scripts.
- Commit after each working step with a clear message. Do not commit data or large binaries.

## 11. Writing rules for the report and slides

- Define every term before first use. Problem first, method second.
- Match claim strength to evidence. Say "on this dataset" when that is the scope.
- Numbers with units and the configuration they came from.
- Plain words, short sentences, active voice.
- No em dashes, no semicolons, no rhetorical questions, no filler openers, no promotional adjectives.
- Avoid decorative AI vocabulary: delve, tapestry, testament, pivotal, crucial, foster, underscore, showcase, landscape, seamless, robust (unless technical), novel framework, state of the art (unless compared).
- Literature review: one short paragraph per paper or group of papers, stating what they did and its limitation relative to our problem.

## 12. Environment

Python 3.11 or newer. Packages: pandas, numpy, scipy, pyarrow, openpyxl, matplotlib, mlxtend, psutil, pytest, hypothesis, ruff, pyyaml, python-docx, graphviz (optional). Pin versions in `requirements.txt` once the environment works.

## 13. Repository layout

```
retail-returns-fim/
  CLAUDE.md
  README.md
  requirements.txt
  configs/            default.yaml, non_product_codes.yaml, sensitivity configs
  data/               raw/, interim/, processed/   (gitignored)
  docs/               proposal.tex, decisions.md
  src/rafim/          load.py, clean.py, link_returns.py, baskets.py,
                      apriori.py, fpgrowth.py, measures.py, rules.py,
                      evaluate.py, bench.py, figures.py, run.py
  tests/
  results/            logs/, tables/, figures/, runs/
  report/             draft.md, references.md, build_docx.py, report.docx
  presentation/       outline.md
  submission/         code.zip
```

## 14. Timeline

| Dates | Phase |
| --- | --- |
| 30 Oct to 2 Nov | Setup, data download, inspection, cleaning, decisions log |
| 3 to 8 Nov | Return linking with tests, baskets and kept baskets |
| 9 to 15 Nov | Apriori and FP-Growth in both modes, correctness gates |
| 16 to 20 Nov | Experiments E1 to E7, tables and figures |
| 21 to 27 Nov | Literature search, report draft, docx build, page check |
| 28 Nov | Final review, code zip, submit on Brightspace before 29 Nov |
| Before the presentation | 5-minute slide outline, every member presents |
