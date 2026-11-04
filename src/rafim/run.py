"""Run the full pipeline and experiments E1 to E7 from one config.

Usage: python -m rafim.run --config configs/default.yaml [--skip-bench]
Writes tables to results/tables/ and run metadata to results/runs/<run_id>/.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from importlib import metadata

import numpy as np
import pandas as pd
import psutil
import yaml

from rafim import clean, link_returns
from rafim.apriori import apriori
from rafim.baskets import Baskets, build, time_split
from rafim.bench import Miner, peak_memory_mb, summarize_times, time_runs
from rafim.evaluate import (
    descriptions,
    holdout_stability,
    label,
    line_return_rate,
    output_change,
    with_codes,
)
from rafim.load import build_parquet
from rafim.measures import item_bitsets
from rafim.paths import PROCESSED, ROOT, RUNS, TABLES, write_log
from rafim.rules import fill_counts, generate

PKGS = ["numpy", "pandas", "scipy", "mlxtend", "pyarrow", "matplotlib", "psutil"]


def log(msg: str) -> None:
    """Print a timestamped progress line."""
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def run_metadata(cfg: dict, run_id: str) -> dict:
    """Collect config, git commit, versions and machine info for a run."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                                             text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", None
    return {
        "run_id": run_id, "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config": cfg, "git_commit": commit, "git_dirty": dirty,
        "python": sys.version, "packages": {p: metadata.version(p) for p in PKGS},
        "machine": {"platform": platform.platform(), "processor": platform.processor(),
                    "cpu_count_logical": psutil.cpu_count(),
                    "ram_gb": round(psutil.virtual_memory().total / 2**30, 1)},
    }


def mine_rules(res: dict, b: Baskets, measure: str, min_conf: float) -> pd.DataFrame:
    """Fill missing counts, generate rules and add stock-code keys."""
    counts = fill_counts(res, item_bitsets(b.full), item_bitsets(b.kept))
    return with_codes(generate(counts, b.n, measure, min_conf), b.items), counts


def dataset_summary(purchases, cancels, stat, b_all: Baskets, train: Baskets,
                    hold: Baskets) -> pd.DataFrame:
    """Figure/table 2: dataset facts after cleaning, for the default scope."""
    cust = purchases.loc[purchases.customer_id.notna()]
    rows = []

    def add(name, value):
        rows.append({"quantity": name, "value": value})

    add("raw rows (both sheets)", 1067371)
    add("rows after removing the duplicated sheet block", 1044848)
    add("purchase lines after cleaning", len(purchases))
    add("purchase invoices after cleaning", purchases.invoice.nunique())
    add("purchase lines with Customer ID", len(cust))
    add("purchase invoices with Customer ID (baskets)", b_all.n)
    add("purchase invoices without Customer ID (excluded)", purchases.loc[
        purchases.customer_id.isna()].invoice.nunique())
    add("customers", cust.customer_id.nunique())
    add("items (stock codes) in baskets", len(b_all.items))
    add("cancellation lines", len(cancels))
    add("cancellation lines linked", int((stat.status == "linked").sum()))
    add("cancellation lines partially linked", int((stat.status == "partially_linked").sum()))
    add("cancellation lines unlinked", int((stat.status == "unlinked").sum()))
    add("first invoice date", str(purchases.invoice_date.min()))
    add("last invoice date", str(purchases.invoice_date.max()))
    for name, b in (("all", b_all), ("train", train), ("hold-out", hold)):
        sz = np.diff(b.full.indptr)
        add(f"baskets ({name})", b.n)
        add(f"basket size mean ({name})", round(float(sz.mean()), 2))
        add(f"basket size median ({name})", float(np.median(sz)))
        add(f"basket size max ({name})", int(sz.max()))
        add(f"line return rate ({name})", round(line_return_rate(b), 5))
        add(f"baskets with a returned item ({name})",
            int((np.diff(b.full.indptr) != np.diff(b.kept.indptr)).sum()))
    return pd.DataFrame(rows)


def bench(cfg: dict, train: Baskets, out_dir) -> tuple[pd.DataFrame, dict]:
    """E1, E2, E7: time and measure both miners under both measures over the grid."""
    miner = Miner(train)
    rows, agree, results = [], [], {}
    over_budget = False
    for ms in cfg["minsup_grid"]:
        if over_budget:
            log(f"skip minsup {ms}: an earlier run exceeded the time budget")
            continue
        for measure in ("standard", "retained"):
            outs = {}
            for algo in ("apriori", "fpgrowth"):
                times, res = time_runs(lambda a=algo, m=measure, x=ms: miner.run(a, m, x),
                                       cfg["repeats"])
                mem = peak_memory_mb(lambda a=algo, m=measure, x=ms: miner.run(a, m, x))
                outs[algo] = res
                rules, _ = mine_rules(res, train, measure, cfg["min_conf"])
                row = {"minsup": ms, "algorithm": algo, "measure": measure,
                       **summarize_times(times), "peak_tracemalloc_mib": mem,
                       "itemsets": len(res), "max_itemset_len": max(map(len, res), default=0),
                       "rules": len(rules)}
                rows.append(row)
                log(f"minsup {ms} {algo:8s} {measure:8s} median {row['runtime_median_s']:.2f}s "
                    f"itemsets {len(res)} rules {len(rules)} mem {mem:.1f}MiB")
                if row["runtime_median_s"] > cfg["time_budget_s"]:
                    over_budget = True
            same = outs["apriori"] == outs["fpgrowth"]
            agree.append({"minsup": ms, "measure": measure, "identical": same,
                          "itemsets_apriori": len(outs["apriori"]),
                          "itemsets_fpgrowth": len(outs["fpgrowth"])})
            results[(ms, measure)] = outs["apriori"]
    pd.DataFrame(agree).to_csv(TABLES / "e7_agreement.csv", index=False)
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "e1_e2_bench.csv", index=False)
    pd.DataFrame(rows).to_json(out_dir / "bench.json", orient="records", indent=1)
    return df, results


def bench_mlxtend(cfg: dict, train: Baskets) -> pd.DataFrame:
    """Extra runtime reference: mlxtend apriori and fpgrowth in standard mode."""
    miner = Miner(train)
    rows = []
    for algo in ("apriori", "fpgrowth"):
        for ms in cfg["minsup_grid"]:
            times, res = time_runs(lambda a=algo, x=ms: miner.run_mlxtend(a, x), cfg["repeats"])
            rows.append({"minsup": ms, "algorithm": f"mlxtend_{algo}", "measure": "standard",
                         **summarize_times(times), "itemsets": len(res)})
            log(f"mlxtend {algo} {ms}: {rows[-1]['runtime_median_s']:.2f}s {len(res)} itemsets")
            if rows[-1]["runtime_median_s"] > cfg["mlxtend_budget_s"]:
                log(f"mlxtend {algo}: over budget, stop at {ms}")
                break
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "e1_mlxtend_bench.csv", index=False)
    return df


def overhead_table(bench_df: pd.DataFrame) -> pd.DataFrame:
    """E2: retained/standard runtime and memory ratios per algorithm and minsup."""
    piv = bench_df.pivot_table(index=["minsup", "algorithm"], columns="measure",
                               values=["runtime_median_s", "peak_tracemalloc_mib"])
    out = pd.DataFrame({
        "runtime_standard_s": piv[("runtime_median_s", "standard")],
        "runtime_retained_s": piv[("runtime_median_s", "retained")],
        "runtime_ratio": piv[("runtime_median_s", "retained")]
        / piv[("runtime_median_s", "standard")],
        "mem_standard_mib": piv[("peak_tracemalloc_mib", "standard")],
        "mem_retained_mib": piv[("peak_tracemalloc_mib", "retained")],
        "mem_ratio": piv[("peak_tracemalloc_mib", "retained")]
        / piv[("peak_tracemalloc_mib", "standard")],
    }).reset_index()
    out.to_csv(TABLES / "e2_overhead.csv", index=False)
    return out


def mine_pair(train: Baskets, minsup: float, min_conf: float):
    """Mine baseline and return-aware itemsets and rules with our Apriori (no timing)."""
    fb, kb = item_bitsets(train.full), item_bitsets(train.kept)
    base = apriori(fb, kb, train.n, minsup, "standard")
    ra = apriori(fb, kb, train.n, minsup, "retained")
    base_rules, base_counts = mine_rules(base, train, "standard", min_conf)
    ra_rules, ra_counts = mine_rules(ra, train, "retained", min_conf)
    return base_counts, ra_counts, base_rules, ra_rules


def e3(cfg, train, results) -> pd.DataFrame:
    """E3 across the grid using the itemsets already mined in bench (or mined now)."""
    rows = []
    for ms in cfg["minsup_grid"]:
        if (ms, "standard") in results:
            base, ra = results[(ms, "standard")], results[(ms, "retained")]
            br, bc = mine_rules(base, train, "standard", cfg["min_conf"])
            rr_, rc = mine_rules(ra, train, "retained", cfg["min_conf"])
        else:
            bc, rc, br, rr_ = mine_pair(train, ms, cfg["min_conf"])
        rows.append({"minsup": ms, **output_change(bc, rc, br, rr_, cfg["top_k"])})
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "e3_output_change.csv", index=False)
    return df


def e4(cfg, train, base_counts, base_rules, desc) -> dict:
    """E4: distribution of rr(X) over baseline itemsets and high-return rules."""
    lrr = line_return_rate(train)
    thr = cfg["high_rr_multiplier"] * lrr
    items = train.items
    its = pd.DataFrame([
        {"itemset": ",".join(items[list(s)]), "size": len(s), "sup": f / train.n,
         "rsup": k / train.n, "rr": 1 - k / f} for s, (f, k) in base_counts.items()
    ])
    its.to_csv(TABLES / "e4_itemsets_main.csv", index=False)
    high = base_rules.loc[base_rules.rr >= thr].sort_values(["rr", "sup"], ascending=False)
    cols = ["key", "sup", "rsup", "conf", "rconf", "lift", "rr"]
    out_rules = high[cols].copy()
    out_rules["antecedent_desc"] = [label(a, desc) for a in high.a_codes]
    out_rules["consequent_desc"] = [label(b, desc) for b in high.b_codes]
    out_rules.to_csv(TABLES / "e4_high_rr_rules.csv", index=False)
    summary = {
        "minsup": cfg["main_minsup"], "line_return_rate_train": lrr,
        "high_rr_threshold": thr, "high_rr_multiplier": cfg["high_rr_multiplier"],
        "itemsets": len(its), "itemsets_rr_zero": int((its.rr == 0).sum()),
        "itemsets_high_rr": int((its.rr >= thr).sum()),
        "itemsets_size2plus": int((its["size"] >= 2).sum()),
        "itemsets_size2plus_high_rr": int(((its["size"] >= 2) & (its.rr >= thr)).sum()),
        "rr_mean": float(its.rr.mean()), "rr_median": float(its.rr.median()),
        "rr_q90": float(its.rr.quantile(0.9)), "rr_max": float(its.rr.max()),
        "rules_baseline": len(base_rules), "rules_baseline_high_rr": len(high),
        "share_rules_baseline_high_rr": len(high) / len(base_rules) if len(base_rules) else 0,
    }
    pd.DataFrame([summary]).to_csv(TABLES / "e4_summary.csv", index=False)
    return summary


def e5(cfg, base_rules, ra_rules, hold: Baskets, hold_censored: Baskets) -> pd.DataFrame:
    """E5: hold-out stability of top-k rules from E1 and E2, also with censored hold-out."""
    rows, per_rule = [], []
    for hold_name, h in (("holdout_all", hold), ("holdout_censored", hold_censored)):
        for run, rules, score in (("baseline", base_rules, "conf"),
                                  ("return_aware", ra_rules, "rconf")):
            for k in cfg["top_k"]:
                res = holdout_stability(rules, score, h, cfg["min_conf"], k)
                pr = res.pop("per_rule")
                pr["run"], pr["k"], pr["holdout"] = run, k, hold_name
                per_rule.append(pr)
                rows.append({"holdout": hold_name, "holdout_baskets": h.n, "run": run, **res})
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "e5_holdout.csv", index=False)
    pd.concat(per_rule).to_csv(TABLES / "e5_holdout_per_rule.csv", index=False)
    return df


def e4_persistence(cfg, train: Baskets, hold: Baskets, base_counts: dict) -> dict:
    """E4b: is the itemset return rate persistent from train to hold-out?

    For baseline itemsets of size >= 2 at the main minsup with at least min_holdout_count
    hold-out baskets, compare rr on train with rr on hold-out (Spearman correlation) and
    compare hold-out rr of itemsets flagged high-rr on train with the others.
    """
    from scipy.stats import mannwhitneyu, spearmanr

    from rafim.measures import counts_for
    thr = cfg["high_rr_multiplier"] * line_return_rate(train)
    sets = [s for s in base_counts if len(s) >= 2]
    hf = counts_for(item_bitsets(hold.full), sets + [s[:k] for s in sets for k in
                                                       range(1, len(s))])
    hk = counts_for(item_bitsets(hold.kept), sets + [s[:k] for s in sets for k in
                                                       range(1, len(s))])
    rows = []
    for s in sets:
        f, k = base_counts[s]
        if hf[s] >= cfg["min_holdout_count"]:
            rows.append({"rr_train": 1 - k / f, "rr_holdout": 1 - hk[s] / hf[s],
                         "flag": (1 - k / f) >= thr})
    d = pd.DataFrame(rows)
    rho = spearmanr(d.rr_train, d.rr_holdout)
    hi, lo = d.loc[d.flag, "rr_holdout"], d.loc[~d.flag, "rr_holdout"]
    mw = mannwhitneyu(hi, lo, alternative="greater")
    out = {"itemsets_compared": len(d), "min_holdout_count": cfg["min_holdout_count"],
           "spearman_rho": float(rho.statistic), "spearman_p": float(rho.pvalue),
           "flagged_train": int(d.flag.sum()),
           "holdout_rr_mean_flagged": float(hi.mean()),
           "holdout_rr_mean_not_flagged": float(lo.mean()),
           "holdout_rr_median_flagged": float(hi.median()),
           "holdout_rr_median_not_flagged": float(lo.median()),
           "share_flagged_still_above_threshold_holdout": float((hi >= thr).mean()),
           "share_not_flagged_above_threshold_holdout": float((lo >= thr).mean()),
           "mannwhitney_u_p_greater": float(mw.pvalue), "threshold": thr}
    pd.DataFrame([out]).to_csv(TABLES / "e4b_rr_persistence.csv", index=False)
    return out


def e5_differing(cfg, purchases, alloc) -> pd.DataFrame:
    """E5b: hold-out stability of the rules on which baseline and return-aware disagree.

    Groups at the main minsup: rules found by both runs, baseline-only rules (dropped by
    the return-aware run) and return-aware-only rules. Run for both partial-return
    policies. Hold-out rconf is measured on hold-out kept baskets under the same policy.
    """
    rows = []
    for policy in ("full", "any"):
        b = build(purchases, alloc, policy, cfg["include_anonymous"])
        tr, ho = time_split(b)
        _, _, br, rr_ = mine_pair(tr, cfg["main_minsup"], cfg["min_conf"])
        groups = {
            "both": (br.loc[br.key.isin(set(rr_.key))], "conf"),
            "baseline_only": (br.loc[~br.key.isin(set(rr_.key))], "conf"),
            "return_aware_only": (rr_.loc[~rr_.key.isin(set(br.key))], "rconf"),
        }
        for name, (rules, score) in groups.items():
            if rules.empty:
                rows.append({"policy": policy, "group": name, "rules": 0})
                continue
            res = holdout_stability(rules, score, ho, cfg["min_conf"], len(rules))
            pr = res.pop("per_rule")
            rows.append({"policy": policy, "group": name, "rules": len(rules),
                         "share_meeting_min_conf": res["share_meeting_min_conf"],
                         "mean_train_conf": float(rules[score].mean()),
                         "mean_rconf_holdout": res["mean_rconf_holdout"],
                         "median_rconf_holdout": float(np.nanmedian(pr.holdout_rconf)),
                         "mean_change_in_confidence": res["mean_change_in_confidence"],
                         "rules_with_antecedent_absent": res["rules_with_antecedent_absent"],
                         "mean_train_rr": float(rules.rr.mean())})
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "e5b_differing_rules.csv", index=False)
    return df


def e6(cfg, purchases, alloc, default_ra_keys: set) -> pd.DataFrame:
    """E6: sensitivity to partial-return policy and to anonymous purchases."""
    rows = []
    ms, mc = cfg["main_minsup"], cfg["min_conf"]
    for v in cfg["sensitivity"]:
        b = build(purchases, alloc, v["partial_return_policy"], v["include_anonymous"])
        tr, ho = time_split(b)
        bc, rc, br, rr_ = mine_pair(tr, ms, mc)
        ch = output_change(bc, rc, br, rr_, [20])
        k = 20
        st_b = holdout_stability(br, "conf", ho, mc, k)
        st_r = holdout_stability(rr_, "rconf", ho, mc, k)
        ra_keys = set(rr_.key)
        rows.append({
            "variant": v["name"], "policy": v["partial_return_policy"],
            "anonymous_included": v["include_anonymous"], "train_baskets": tr.n,
            "holdout_baskets": ho.n, "line_return_rate_train": line_return_rate(tr),
            "itemsets_baseline": ch["itemsets_baseline"],
            "itemsets_return_aware": ch["itemsets_return_aware"],
            "itemsets_dropped": ch["itemsets_only_baseline"],
            "rules_baseline": ch["rules_baseline"], "rules_return_aware": ch["rules_return_aware"],
            "rules_only_baseline": ch["rules_only_baseline"],
            "rules_only_return_aware": ch["rules_only_return_aware"],
            "top20_overlap": ch["top20_overlap"],
            "kendall_tau": ch["kendall_tau_common_rules"],
            "holdout_top20_share_baseline": st_b["share_meeting_min_conf"],
            "holdout_top20_share_return_aware": st_r["share_meeting_min_conf"],
            "jaccard_ra_rules_vs_default": (len(ra_keys & default_ra_keys)
                                            / len(ra_keys | default_ra_keys))
            if (ra_keys | default_ra_keys) else np.nan,
        })
        log(f"E6 {v['name']}: {rows[-1]}")
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "e6_sensitivity.csv", index=False)
    return df


def top_rules_table(base_rules, ra_rules, desc, k=10) -> pd.DataFrame:
    """Table 6: top-k rules under baseline and return-aware with all measures."""
    cols = ["key", "sup", "rsup", "conf", "rconf", "lift", "rr"]
    parts = []
    for run, rules in (("baseline", base_rules), ("return_aware", ra_rules)):
        t = rules.head(k).copy()
        t.insert(0, "rank", range(1, len(t) + 1))
        t.insert(0, "run", run)
        t["antecedent_desc"] = [label(a, desc) for a in t.a_codes]
        t["consequent_desc"] = [label(b, desc) for b in t.b_codes]
        t["in_other_top"] = t.key.isin(
            (ra_rules if run == "baseline" else base_rules).key.head(k))
        parts.append(t[["run", "rank", *cols, "antecedent_desc", "consequent_desc",
                        "in_other_top"]])
    df = pd.concat(parts, ignore_index=True)
    df.to_csv(TABLES / "top_rules.csv", index=False)
    return df


def main() -> None:
    """Entry point: run every step for the given config."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--skip-bench", action="store_true", help="reuse no timings, skip E1/E2")
    ap.add_argument("--skip-mlxtend", action="store_true")
    ap.add_argument("--only", choices=["e5b", "e4b"],
                    help="run setup and one extra analysis only")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{cfg['run_name']}"
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata.json").write_text(json.dumps(run_metadata(cfg, run_id), indent=1))
    t0 = time.perf_counter()

    log("load / clean / link")
    build_parquet()
    purchases, cancels = clean.run()
    alloc = link_returns.run()
    stat = pd.read_parquet(PROCESSED / "cancellation_status.parquet")
    if args.only == "e5b":
        log("E5b differing rules")
        print(e5_differing(cfg, purchases, alloc).to_string())
        return
    if args.only == "e4b":
        tr_, ho_ = time_split(build(purchases, alloc, cfg["partial_return_policy"],
                                    cfg["include_anonymous"]))
        bc_, _, _, _ = mine_pair(tr_, cfg["main_minsup"], cfg["min_conf"])
        log("E4b rr persistence")
        print(json.dumps(e4_persistence(cfg, tr_, ho_, bc_), indent=1))
        return

    b = build(purchases, alloc, cfg["partial_return_policy"], cfg["include_anonymous"])
    train, hold = time_split(b)
    end = purchases.invoice_date.max()
    cutoff = end - pd.Timedelta(days=cfg["censor_days"])
    hold_c = hold.subset((hold.meta.invoice_date <= cutoff).to_numpy())
    desc = descriptions(purchases)
    dataset_summary(purchases, cancels, stat, b, train, hold).to_csv(
        TABLES / "dataset_summary.csv", index=False)
    write_log("05_baskets", {"baskets": b.n, "train": train.n, "holdout": hold.n,
                             "holdout_censored": hold_c.n, "censor_cutoff": cutoff,
                             "items": len(b.items)})

    results = {}
    if not args.skip_bench:
        log("E1/E2/E7 bench")
        bench_df, results = bench(cfg, train, out_dir)
        overhead_table(bench_df)
        if not args.skip_mlxtend:
            log("mlxtend reference")
            bench_mlxtend(cfg, train)

    log("E3 output change")
    e3(cfg, train, results)
    log("main operating point")
    bc, _, br, rr_ = mine_pair(train, cfg["main_minsup"], cfg["min_conf"])
    br.drop(columns=["antecedent", "consequent"]).to_csv(TABLES / "rules_baseline_main.csv",
                                                         index=False)
    rr_.drop(columns=["antecedent", "consequent"]).to_csv(
        TABLES / "rules_return_aware_main.csv", index=False)
    top_rules_table(br, rr_, desc)
    log("E4 return rates")
    e4(cfg, train, bc, br, desc)
    e4_persistence(cfg, train, hold, bc)
    log("E5 hold-out")
    e5(cfg, br, rr_, hold, hold_c)
    log("E5b differing rules")
    e5_differing(cfg, purchases, alloc)
    log("E6 sensitivity")
    e6(cfg, purchases, alloc, set(rr_.key))
    (out_dir / "elapsed_s.txt").write_text(f"{time.perf_counter() - t0:.1f}\n")
    log(f"done in {time.perf_counter() - t0:.0f}s, run {run_id}")


if __name__ == "__main__":
    main()
