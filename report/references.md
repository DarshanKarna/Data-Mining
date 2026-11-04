# References

Two groups. Group A was verified before this project phase (CLAUDE.md section 9). Group B was
added in Phase 5 (2026-10-29). For every Group B entry the record was opened and authors, title,
venue, year, pages and DOI were checked against the URLs listed. The "Used for" line states which
facts the report takes from the source. Nothing else is claimed about these papers.

Final numbering in the report follows order of first citation. See `report/draft.md`.

## Group A (from CLAUDE.md section 9)

- R. Agrawal and R. Srikant, "Fast algorithms for mining association rules in large databases," in Proc. 20th Int. Conf. Very Large Data Bases (VLDB), Santiago, Chile, 1994, pp. 487-499.
- J. Han, J. Pei, and Y. Yin, "Mining frequent patterns without candidate generation," in Proc. ACM SIGMOD Int. Conf. Manage. Data, Dallas, TX, USA, 2000, pp. 1-12, doi: 10.1145/335191.335372.
- D. Chen, "Online Retail II," UCI Machine Learning Repository, 2012, doi: 10.24432/C5CG6D.
- shahashmi, "market-basket-analysis," GitHub repository. [Online]. Available: https://github.com/shahashmi/market-basket-analysis
- D. Karl, "Forecasting e-commerce consumer returns: A systematic literature review," Manage. Rev. Quart., vol. 75, no. 3, pp. 1-56, 2025, doi: 10.1007/s11301-024-00436-x.
- Q. H. Duong, L. Zhou, M. Meng, T. V. Nguyen, P. Ieromonachou, and D. T. Nguyen, "Understanding product returns: A systematic literature review using machine learning and bibliometric analysis," Int. J. Prod. Econ., vol. 243, Art. no. 108340, 2022, doi: 10.1016/j.ijpe.2021.108340.
- J. Li, J. He, and Y. Zhu, "E-tail product return prediction via hypergraph-based local graph cut," in Proc. 24th ACM SIGKDD Int. Conf. Knowl. Discovery Data Mining, 2018, pp. 519-527, doi: 10.1145/3219819.3219829.
- G. Shang, E. C. McKie, M. E. Ferguson, and M. R. Galbreth, "Using transactions data to improve consumer returns forecasting," J. Oper. Manage., vol. 66, no. 3, pp. 326-348, 2020, doi: 10.1002/joom.1071.
- P. Ambilkar, V. Dohale, A. Gunasekaran, and V. Bilolikar, "Product returns management: A comprehensive review and future research agenda," Int. J. Prod. Res., vol. 60, no. 12, pp. 3920-3944, 2022, doi: 10.1080/00207543.2021.1933645.
- W. Gan, J. C.-W. Lin, P. Fournier-Viger, H.-C. Chao, V. S. Tseng, and P. S. Yu, "A survey of utility-oriented pattern mining," IEEE Trans. Knowl. Data Eng., vol. 33, no. 4, pp. 1306-1327, 2021, doi: 10.1109/TKDE.2019.2942594.
- K. Meißner, A. B. Stevenson, and J. Rieck, "Identifying non-intuitive relationships within returns data of a furniture online-shop using temporal data mining," in Recent Challenges in Intelligent Information and Database Systems (ACIIDS 2022), Commun. Comput. Inf. Sci., vol. 1716. Singapore: Springer, 2022, pp. 299-312, doi: 10.1007/978-981-19-8234-7_24.
- D. Chen, S. L. Sain, and K. Guo, "Data mining for the online retail industry: A case study of RFM model-based customer segmentation using data mining," J. Database Marketing Customer Strategy Manage., vol. 19, no. 3, pp. 197-208, 2012, doi: 10.1057/dbm.2012.17.
- S. Raschka, "MLxtend: Providing machine learning and data science utilities and extensions to Python's scientific computing stack," J. Open Source Softw., vol. 3, no. 24, Art. no. 638, 2018, doi: 10.21105/joss.00638.
- L. Bustio-Martínez, R. Cumplido, M. Letras, R. Hernández-León, C. Feregrino-Uribe, and J. Hernández-Palancar, "FPGA/GPU-based acceleration for frequent itemsets mining: A comprehensive review," ACM Comput. Surv., vol. 54, no. 9, 2022, doi: 10.1145/3472289.

## Group B (added and checked 2026-10-29)

- F. Zhao, D. Agrawal, A. El Abbadi, and A. Metwally, "SpaceSaving±: An optimal algorithm for frequency estimation and frequent items in the bounded-deletion model," Proc. VLDB Endow., vol. 15, no. 6, pp. 1215-1227, 2022, doi: 10.14778/3514061.3514068.
  - Checked: https://www.vldb.org/pvldb/vol15/p1215-zhao.pdf (full paper, title page) and https://api.crossref.org/works/10.14778/3514061.3514068
  - Used for: frequent items when a bounded fraction of insertions is later deleted. Deterministic algorithms with a space lower bound. Works on single items in a stream, and deletions are bounded by a global ratio, not linked to specific insertions.
- T. Martin, G. Francoeur, and P. Valtchev, "CICLAD: A fast and memory-efficient closed itemset miner for streams," in Proc. 26th ACM SIGKDD Int. Conf. Knowl. Discovery Data Mining, 2020, pp. 1810-1818, doi: 10.1145/3394486.3403232.
  - Checked: https://api.crossref.org/works/10.1145/3394486.3403232, https://arxiv.org/abs/2007.01946 and the arXiv PDF (problem setting, section 2)
  - Used for: sliding-window closed itemset miner. When the window slides it removes an obsolete transaction t_o (D- = D - {t_o}) and updates the closed itemsets whose support drops. Removal is of whole transactions.
- A. Nestler, N. Karessli, K. Hajjar, R. Weffer, and R. Shirvany, "SizeFlags: Reducing size and fit related returns in fashion e-commerce," in Proc. 27th ACM SIGKDD Conf. Knowl. Discovery Data Mining, 2021, pp. 3432-3440, doi: 10.1145/3447548.3467160.
  - Checked: https://api.crossref.org/works/10.1145/3447548.3467160 and https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3447548.3467160 (abstract; arXiv 2106.03532)
  - Used for: Bayesian model on weakly annotated customer data, with expert and computer-vision priors, that flags size and fit issues. Evaluated with large-scale A/B tests in production. Targets size-related returns in fashion.
- W. Gan, S. Wan, J. Chen, C.-M. Chen, and L. Qiu, "TopHUI: Top-k high-utility itemset mining with negative utility," in Proc. IEEE Int. Conf. Big Data, 2020, pp. 5350-5359, doi: 10.1109/BigData50022.2020.9378288.
  - Checked: https://api.crossref.org/works/10.1109/bigdata50022.2020.9378288 and https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/BigData50022.2020.9378288 (abstract)
  - Used for: top-k high-utility itemsets in databases with both positive and negative utility, using a positive-and-negative utility list and threshold-raising and pruning strategies.
- J. He, X. Han, X. Wan, and J. Wang, "Efficient skyline frequent-utility itemset mining algorithm on massive data," IEEE Trans. Knowl. Data Eng., vol. 36, no. 7, pp. 3009-3023, 2024, doi: 10.1109/TKDE.2024.3349454.
  - Checked: https://api.crossref.org/works/10.1109/tkde.2024.3349454 and https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/TKDE.2024.3349454 (abstract)
  - Used for: skyline frequent-utility itemset mining that considers frequency and utility together without a threshold. Algorithm PSI* with prefix-based partitioning and four pruning strategies.
- J. M. Luna, P. Fournier-Viger, and S. Ventura, "Frequent itemset mining: A 25 years review," WIREs Data Mining Knowl. Discovery, vol. 9, no. 6, Art. no. e1329, 2019, doi: 10.1002/widm.1329.
  - Checked: https://api.crossref.org/works/10.1002/widm.1329 (record with abstract)
  - Used for: review of FIM algorithms since the early 1990s. Cost grows exponentially with the number of items, and memory use is significant.
- Z. Li, F. Chen, J. Wu, Z. Liu, and W. Liu, "Efficient weighted probabilistic frequent itemset mining in uncertain databases," Expert Syst., vol. 38, no. 5, Art. no. e12551, 2020, doi: 10.1111/exsy.12551.
  - Checked: https://api.crossref.org/works/10.1111/exsy.12551 (record with abstract; Crossref issued date 2020-04-07)
  - Used for: in uncertain databases an item appears in a transaction only with some probability. Frequency is defined by expected support or by probabilistic support. The paper adds item weights.
- Y. Tong, L. Chen, Y. Cheng, and P. S. Yu, "Mining frequent itemsets over uncertain databases," Proc. VLDB Endow., vol. 5, no. 11, pp. 1650-1661, 2012, doi: 10.14778/2350229.2350277.
  - Checked: https://api.crossref.org/works/10.14778/2350229.2350277 (record with abstract)
  - Used for: support of an itemset is a random variable over uncertain data. The two definitions are expected-support-based and probabilistic frequent itemsets.
- I. D. Hunyadi, N. Constantinescu, and O.-A. Țicleanu, "Efficient discovery of association rules in e-commerce: Comparing candidate generation and pattern growth techniques," Appl. Sci., vol. 15, no. 10, Art. no. 5498, 2025, doi: 10.3390/app15105498.
  - Checked: https://api.crossref.org/works/10.3390/app15105498 and https://api.semanticscholar.org/graph/v1/paper/DOI:10.3390/app15105498 (abstract). The MDPI page returned HTTP 403 to automated access, so the full text was not read. The report makes no claim about their dataset.
  - Used for: compares Apriori and FP-Growth in RapidMiner on e-commerce data on execution time, memory, number of rules and rule strength, with SPSS analysis. Reports FP-Growth faster on large data.

### Considered and not used

- B. Vo, T. Le, T.-P. Hong, and B. Le, "Fast updated frequent-itemset lattice for transaction deletion," Data Knowl. Eng., vol. 96-97, pp. 78-89, 2015, doi: 10.1016/j.datak.2015.04.006. Metadata confirmed on Crossref, but no abstract or full text could be opened, so its content cannot be described. Not cited.
