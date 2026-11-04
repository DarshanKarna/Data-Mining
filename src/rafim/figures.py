"""Regenerate every report figure from results/tables/ (PDF and 300 dpi PNG, 3.5 in wide).

Usage: python -m rafim.figures
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from rafim.paths import FIGURES, TABLES

WIDTH = 3.5
COLORS = {"standard": "#1f4e79", "retained": "#c55a11"}
NAMES = {"standard": "baseline", "retained": "return-aware"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 1.1, "lines.markersize": 3.5,
})


def minsup_axis(ax, grid) -> None:
    """Log x axis over the minsup grid, decreasing to the right, with plain tick labels."""
    ax.set_xscale("log")
    ax.set_xticks(grid)
    ax.set_xticklabels([f"{g:g}" for g in grid], rotation=45, ha="right")
    ax.minorticks_off()
    ax.set_xlim(max(grid) * 1.15, min(grid) / 1.15)
    ax.set_xlabel("minimum support (fraction of train baskets)")


def save(fig, name: str) -> None:
    """Save a figure as PDF and 300 dpi PNG in results/figures/."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def workflow() -> None:
    """Figure 1: pipeline from raw workbook to evaluation."""
    steps = [
        ("Load", "2 sheets, 1,067,371 rows\nParquet cache"),
        ("Clean", "drop sheet overlap, non-products,\nstock adjustments"),
        ("Split", "purchases | cancellations (C)"),
        ("Link returns", "walk back over earlier purchases\nof same customer and stock code"),
        ("Baskets", "full basket t  |  kept basket k(t)\nsparse matrices, tid bitsets"),
        ("Mine (train)", "Apriori, FP-Growth\nmeasure = standard | retained"),
        ("Rules", "sup, rsup, conf, rconf, lift, rr"),
        ("Evaluate", "E1-E7: cost, output change, rr,\nhold-out stability, sensitivity"),
    ]
    fig, ax = plt.subplots(figsize=(WIDTH, 4.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(steps))
    ax.axis("off")
    h = 0.72
    for i, (title, body) in enumerate(steps):
        y = len(steps) - i - 0.5
        accent = title in ("Link returns", "Baskets") or title.startswith("Mine")
        box = FancyBboxPatch((0.03, y - h / 2), 0.94, h, boxstyle="round,pad=0.01,rounding_size=0.03",
                             linewidth=0.8, edgecolor="#333333",
                             facecolor="#fbe5d6" if accent else "#eef2f7")
        ax.add_patch(box)
        ax.text(0.06, y, title, ha="left", va="center", fontweight="bold", fontsize=7.5)
        ax.text(0.33, y, body, ha="left", va="center", fontsize=6.6, linespacing=1.15)
        if i < len(steps) - 1:
            ax.annotate("", xy=(0.5, y - h / 2 - 0.26), xytext=(0.5, y - h / 2),
                        arrowprops={"arrowstyle": "-|>", "lw": 0.8, "color": "#333333"})
    save(fig, "fig1_workflow")


def runtime() -> None:
    """Figure 3: median runtime vs minimum support, both algorithms and measures."""
    df = pd.read_csv(TABLES / "e1_e2_bench.csv")
    fig, ax = plt.subplots(figsize=(WIDTH, 2.3))
    for algo, ls, mk in (("apriori", "-", "o"), ("fpgrowth", "--", "s")):
        for m in ("standard", "retained"):
            d = df[(df.algorithm == algo) & (df.measure == m)].sort_values("minsup")
            yerr = [d.runtime_median_s - d.runtime_min_s, d.runtime_max_s - d.runtime_median_s]
            ax.errorbar(d.minsup, d.runtime_median_s, yerr=yerr, ls=ls, marker=mk,
                        color=COLORS[m], capsize=1.5, elinewidth=0.6,
                        label=f"{'Apriori' if algo == 'apriori' else 'FP-Growth'}, {NAMES[m]}")
    ax.set_yscale("log")
    minsup_axis(ax, sorted(df.minsup.unique()))
    ax.set_ylabel("runtime (s), median of 3 repeats")
    ax.grid(True, which="major", lw=0.3, alpha=0.5)
    ax.legend(frameon=False, ncol=1)
    save(fig, "fig3_runtime")


def itemsets() -> None:
    """Figure 4: counts under the baseline and the share removed by the return-aware run."""
    df = pd.read_csv(TABLES / "e1_e2_bench.csv")
    e3 = pd.read_csv(TABLES / "e3_output_change.csv").sort_values("minsup")
    d = df[df.algorithm == "apriori"]
    grid = sorted(df.minsup.unique())
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 3.6), sharex=True)
    for m, mk in (("standard", "o"), ("retained", "s")):
        s_ = d[d.measure == m].sort_values("minsup")
        axes[0].plot(s_.minsup, s_.itemsets, marker=mk, color=COLORS[m], label=f"itemsets, {NAMES[m]}")
        r = s_[s_.rules > 0]
        axes[0].plot(r.minsup, r.rules, marker=mk, ls=":", color=COLORS[m], label=f"rules, {NAMES[m]}")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("count")
    axes[0].legend(frameon=False, fontsize=6, ncol=2, loc="upper left")
    share_i = 100 * e3.itemsets_only_baseline / e3.itemsets_baseline
    r = e3[e3.rules_baseline > 0]
    share_r = 100 * r.rules_only_baseline / r.rules_baseline
    axes[1].plot(e3.minsup, share_i, marker="o", color="#444444", label="itemsets dropped")
    axes[1].plot(r.minsup, share_r, marker="s", ls=":", color="#444444", label="rules dropped")
    axes[1].set_ylabel("% of baseline output removed")
    minsup_axis(axes[1], grid)
    axes[1].set_ylim(bottom=0)
    axes[1].legend(frameon=False, fontsize=6)
    axes[0].set_title("(a) output size", fontsize=7)
    axes[1].set_title("(b) share of baseline output not reported by the return-aware run",
                      fontsize=7)
    for ax in axes:
        ax.grid(True, which="major", lw=0.3, alpha=0.5)
    axes[0].tick_params(labelbottom=False)
    axes[0].set_xlabel("")
    fig.tight_layout(h_pad=0.6)
    save(fig, "fig4_itemsets")


def rr_distribution() -> None:
    """Figure 5: distribution of rr(X) over baseline itemsets at the main minsup."""
    its = pd.read_csv(TABLES / "e4_itemsets_main.csv")
    summ = pd.read_csv(TABLES / "e4_summary.csv").iloc[0]
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 1.9), gridspec_kw={"width_ratios": [1, 2.6]})
    zero = (its.rr == 0).mean()
    axes[0].bar(["rr = 0", "rr > 0"], [zero, 1 - zero], color=["#9aa7b8", COLORS["retained"]])
    axes[0].set_ylabel("share of itemsets")
    axes[0].set_ylim(0, 1)
    pos = its.loc[its.rr > 0, "rr"]
    bins = np.linspace(0, max(0.2, pos.max() if len(pos) else 0.2), 25)
    for size_lbl, sel, col in (("size 1", its["size"] == 1, "#9aa7b8"),
                               ("size 2+", its["size"] >= 2, COLORS["retained"])):
        axes[1].hist(its.loc[sel & (its.rr > 0), "rr"], bins=bins, alpha=0.75, color=col,
                     label=size_lbl)
    axes[1].axvline(summ.high_rr_threshold, color="black", lw=0.8, ls="--")
    axes[1].text(summ.high_rr_threshold, axes[1].get_ylim()[1] * 0.92,
                 f" high-rr threshold\n {summ.high_rr_threshold:.4f}", fontsize=6, va="top")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("itemset return rate rr(X), rr > 0 only")
    axes[1].set_ylabel("itemsets")
    axes[1].legend(frameon=False, loc="center right")
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig5_rr_distribution")


def holdout() -> None:
    """Figure 7: (a) hold-out stability of rules the runs agree or disagree on (E5b),
    (b) persistence of the itemset return rate from train to hold-out (E4b)."""
    e5b = pd.read_csv(TABLES / "e5b_differing_rules.csv")
    e4b = pd.read_csv(TABLES / "e4b_rr_persistence.csv").iloc[0]
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.0), gridspec_kw={"width_ratios": [1.7, 1]})
    groups = ["both", "baseline_only", "return_aware_only"]
    labels = ["both", "baseline\nonly", "return-aware\nonly"]
    x = np.arange(len(groups))
    for j, (policy, col) in enumerate((("full", "#1f4e79"), ("any", "#c55a11"))):
        d = e5b[e5b.policy == policy].set_index("group").loc[groups]
        bars = axes[0].bar(x + (j - 0.5) * 0.36, d.share_meeting_min_conf, width=0.36, color=col,
                           label=f"policy {policy}")
        for b_, n in zip(bars, d.rules):
            axes[0].text(b_.get_x() + b_.get_width() / 2, max(b_.get_height(), 0) + 0.03,
                         f"{int(n)}", ha="center", va="bottom", fontsize=5.5, rotation=90)
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 1.25)
    axes[0].set_ylabel("share with hold-out rconf >= 0.5")
    axes[0].legend(frameon=False, fontsize=6, loc="upper right", ncol=2)
    axes[0].set_title("(a) rules at minsup 0.005 (number = rules)", fontsize=7)
    vals = [e4b.share_flagged_still_above_threshold_holdout,
            e4b.share_not_flagged_above_threshold_holdout]
    axes[1].bar(["flagged\non train", "not\nflagged"], vals, color=["#c55a11", "#9aa7b8"])
    for i, v in enumerate(vals):
        axes[1].text(i, v + 0.01, f"{v:.2f}", ha="center", fontsize=6)
    axes[1].set_ylabel("share above rr threshold on hold-out")
    axes[1].set_title(f"(b) rr persistence, n={int(e4b.itemsets_compared)}", fontsize=7)
    axes[1].set_ylim(0, max(vals) * 1.25)
    for ax in axes:
        ax.grid(True, axis="y", lw=0.3, alpha=0.5)
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig7_holdout")


def main() -> None:
    """Build every figure."""
    workflow()
    runtime()
    itemsets()
    rr_distribution()
    holdout()


if __name__ == "__main__":
    main()
