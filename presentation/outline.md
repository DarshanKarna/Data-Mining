# Presentation outline (5 minutes, two speakers)

Each slide has one main point. Times are targets. Every member must present, so the split is
even: Speaker A covers the problem and method (slides 1 to 4), Speaker B covers results and
conclusions (slides 5 to 8). Numbers come from `results/tables/` and match the report.

| # | Speaker | Time | Main point | Visual |
| --- | --- | --- | --- | --- |
| 1 | A | 0:20 | Title, group, members | Title only |
| 2 | A | 0:40 | Standard support counts items the customer later returned | One basket drawn twice: t at checkout, k(t) after a return |
| 3 | A | 0:45 | We link each cancellation to the purchase it reverses | Table II (linking outcome): 88.6% of 17,974 lines linked |
| 4 | A | 0:45 | Retained support keeps pruning, so both algorithms change in one place | Fig. 1 workflow, with rsup formula and the anti-monotone proof in one line |
| 5 | B | 0:40 | The extra count doubles Apriori time and costs FP-Growth nothing | Fig. 2 runtime vs minimum support |
| 6 | B | 0:40 | Under the default policy the output barely changes | Fig. 3 (b): 0.8% to 4.3% of itemsets dropped, top-50 identical at 0.005 |
| 7 | B | 0:45 | The return rate flags some bundles, but filtering did not make rules more stable | Table V (cherry lights, rr 0.32) and Fig. 5 (a) and (b) |
| 8 | B | 0:35 | Conclusion: report rsup and rr next to sup and conf, test on higher-return data | Three bullet takeaways |

Total: 5:10 with transitions, so speak slightly faster on slides 5 and 6 if time is short.

## Speaker notes

**Slide 1 (A).** Name the project and both members.

**Slide 2 (A).** Apriori and FP-Growth count a basket as it stood at checkout. In Online
Retail II returns are separate invoices starting with C, and analyses often delete them, so a
returned item still counts. Bundles built on such patterns promote items that come back.

**Slide 3 (A).** A cancellation has a customer, a stock code, a date and a quantity, but no
invoice reference. We walk back over that customer's earlier purchases of the same code. 15,933
of 17,974 lines link fully. The median lag is 10.9 days, and 90% happen within 90 days.

**Slide 4 (A).** k(t) is the basket minus fully returned items. rsup(X) counts baskets where X
is in k(t). If X is in Y and Y is in k(t), X is in k(t), so rsup is anti-monotone. Apriori
keeps a second counter, FP-Growth builds its tree from kept baskets. Both algorithms agree
exactly in 18 of 18 settings and match mlxtend.

**Slide 5 (B).** Return-aware Apriori takes 1.6 to 2.3 times as long because each candidate
needs a second bitset. Return-aware FP-Growth takes 0.86 to 1.12 times as long. Same laptop for
all runs.

**Slide 6 (B).** Only 0.77% of basket items count as returned. At minimum support 0.005 we lose
52 of 3,761 itemsets and the top-50 rules are the same. With the "any" policy the change is
bigger: 270 itemsets and a quarter of the top-20 rules.

**Slide 7 (B).** 174 of 2,638 rules (6.6%) have a return rate above twice the average. The
cherry light pair loses 32% of its baskets to returns. But rules the return-aware run removed
held on the next year as often as the others (81% against 80%). The return-rate flag persists
weakly: 35% of flagged itemsets stay high against 16% of others.

**Slide 8 (B).** Takeaways: (1) the change is cheap and keeps pruning, (2) on this dataset it
changes little and did not improve stability, (3) use rsup and rr as extra columns that show
which bundles customers keep. Next: data with more returns, partial-return weighting.
