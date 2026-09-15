#!/usr/bin/env python3
"""Generates comparison plots for the Hydron evaluation from pilot/run_log.csv.

Reads the single source of truth (pilot/run_log.csv) and produces PNGs into
results/. Every category below is derived directly from real, human-verified
columns already in the CSV (loudness_class, harness_surfaced,
pointed_at_real_cause, repair_succeeded, grounding_class) plus keyword checks
against repair_succeeded's free-text field for verification tier - nothing
here is invented or estimated.

Run (from stm32-pilot/):
    source .venv/bin/activate
    python3 results/make_plots.py

Safe to re-run any time run_log.csv changes - each run overwrites the same
PNG filenames.
"""
import csv
import os
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PILOT_ROOT = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PILOT_ROOT, "pilot", "run_log.csv")
OUT_DIR = SCRIPT_DIR

# A small, consistent palette used across every chart - colorblind-safe,
# fixed hue-to-meaning mapping so the same color always means the same thing.
C_GOOD = "#2A9D6B"      # correct / success / dynamically verified
C_STATIC = "#5B8DEF"    # correct but only statically verified
C_UNCITED = "#B8860B"   # uncited / unverified claim
C_BAD = "#D64545"       # wrong / failed / confident_wrong
C_NEUTRAL = "#8A8F98"   # n/a, structural, other

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#444",
    "axes.grid": True,
    "grid.color": "#e0e0e0",
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "font.size": 10,
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "axes.titleweight": "medium",
})


def load_rows():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("run_id")]
    return rows


def verification_tier(row):
    """Classify repair_succeeded's free text into one honest tier.
    Only ever reads what a human already wrote into the CSV - no inference
    beyond keyword matching on that text."""
    rs = (row["repair_succeeded"] or "").lower()
    if rs.startswith("no"):
        return "failed"
    if "dynamically confirmed" in rs or "dynamically verified" in rs:
        return "dynamic"
    if "unverified" in rs:
        return "unverified"
    if "yes" in rs:
        return "static"  # yes + some form of rebuild/verification, not dynamic
    return "n/a"


def main():
    rows = load_rows()
    harness = [r for r in rows if r["half"] == "harness"]
    generation = [r for r in rows if r["half"] == "generation"]
    n_total, n_harness, n_gen = len(rows), len(harness), len(generation)

    # ---- Plot 1: fault-localization -> repair funnel, by loudness class ----
    classes = ["L0", "L1", "L2", "L3"]
    surfaced = Counter()
    pointed = Counter()
    repaired = Counter()
    class_n = Counter()
    for r in harness:
        cls = r["loudness_class"]
        if cls not in classes:
            continue
        class_n[cls] += 1
        if r["harness_surfaced"].strip().lower() == "yes":
            surfaced[cls] += 1
        if r["pointed_at_real_cause"].strip().lower().startswith("yes"):
            pointed[cls] += 1
        if verification_tier(r) in ("dynamic", "static", "unverified"):
            repaired[cls] += 1

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    x = range(len(classes))
    w = 0.25
    b1 = ax.bar([i - w for i in x], [surfaced[c] for c in classes], width=w,
                label="Surfaced (found it)", color=C_STATIC)
    b2 = ax.bar([i for i in x], [pointed[c] for c in classes], width=w,
                label="Pointed at real cause", color=C_GOOD)
    b3 = ax.bar([i + w for i in x], [repaired[c] for c in classes], width=w,
                label="Correct repair applied", color=C_BAD if False else "#2E7D5B")
    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.annotate(str(int(h)), (bar.get_x() + bar.get_width() / 2, h),
                            ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{c}\n(n={class_n[c]})" for c in classes])
    ax.set_ylabel("Count of runs")
    ax.set_title(f"Fault-localization -> repair funnel by defect class\n"
                 f"Harness-half runs, n={n_harness} (real n per class shown on x-axis)")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_ylim(0, max(class_n.values()) + 3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "1_funnel_by_defect_class.png"), dpi=160)
    plt.close(fig)

    # ---- Plot 2: verification tier, all harness runs ----
    tiers = Counter(verification_tier(r) for r in harness)
    tier_order = ["dynamic", "static", "unverified", "failed"]
    tier_labels = {
        "dynamic": "Dynamically verified\n(real Renode pass/fail)",
        "static": "Statically verified\n(rebuilt / source-diff match)",
        "unverified": "Plausible, unverified\n(no rebuild attempted)",
        "failed": "Repair failed\n(wrong diagnosis or no real fix)",
    }
    tier_colors = {"dynamic": C_GOOD, "static": C_STATIC, "unverified": C_UNCITED, "failed": C_BAD}
    vals = [tiers.get(t, 0) for t in tier_order]
    short_labels = ["Dynamically\nverified", "Statically\nverified",
                    "Plausible,\nunverified", "Repair\nfailed"]
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    bars = ax.bar(short_labels, vals, color=[tier_colors[t] for t in tier_order], width=0.6)
    for bar, v in zip(bars, vals):
        if v > 0:
            ax.annotate(f"{v}  ({v/n_harness:.0%})", (bar.get_x() + bar.get_width() / 2, v),
                        ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Count of harness-half runs")
    ax.set_title(f"Verification tier of every seeded-defect repair\n"
                 f"n={n_harness} harness-half runs (plausible ≠ verified)")
    ax.set_ylim(0, max(vals) + 2.2)
    # Explains what each tier means below the axis, out of the way of the bars.
    caption = ("Dynamic = real Renode pass/fail.  Static = rebuilt or byte-exact source match.\n"
               "Unverified = plausible fix, no rebuild attempted.  Failed = wrong diagnosis or no real edit.")
    fig.text(0.5, -0.01, caption, ha="center", va="top", fontsize=8, color="#444")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(os.path.join(OUT_DIR, "2_verification_tier.png"), dpi=160, bbox_inches="tight")
    plt.close(fig)

    # ---- Plot 3: generation grounding, A-ON vs A-OFF ----
    gclass_order = ["grounded_correct", "lucky_correct", "uncited", "confident_wrong"]
    gclass_labels = {
        "grounded_correct": "Grounded &\ncorrect",
        "lucky_correct": "Correct,\nnot grounded",
        "uncited": "Declined to\nassert unverified",
        "confident_wrong": "Confident claim,\nnever checked",
    }
    gclass_colors = {"grounded_correct": C_GOOD, "lucky_correct": C_UNCITED,
                      "uncited": C_STATIC, "confident_wrong": C_BAD}
    # n=1 per (task, condition) cell - a grouped bar chart of 4 categories would
    # either hide the real pairing or mislead on color-vs-condition. A small,
    # explicit outcome grid shows exactly what happened, task by task.
    task_names = {"GenC": "USART baud formula\n(register-level fact)",
                  "GenD": "GPIO AF7 mapping\n(cross-document fact)"}
    tasks = ["GenC", "GenD"]
    conditions = ["A-ON", "A-OFF"]
    cell = {}
    for r in generation:
        task = r["run_id"].split("-")[0]
        cell[(task, r["condition"])] = r["grounding_class"]

    fig, ax = plt.subplots(figsize=(8, 4.6))
    for ti, task in enumerate(tasks):
        for ci, cond in enumerate(conditions):
            g = cell.get((task, cond), "n/a")
            color = gclass_colors.get(g, C_NEUTRAL)
            ax.add_patch(plt.Rectangle((ci, len(tasks) - 1 - ti), 0.92, 0.92,
                                        facecolor=color, edgecolor="#333", linewidth=1.2))
            ax.text(ci + 0.46, len(tasks) - 1 - ti + 0.46,
                    gclass_labels[g],  # already 2-line, fits within the cell
                    ha="center", va="center", fontsize=10, color="white", weight="bold",
                    linespacing=1.4)
    ax.set_xlim(0, len(conditions))
    ax.set_ylim(0, len(tasks))
    ax.set_xticks([0.46, 1.46])
    ax.set_xticklabels(["Citation explicitly\ninstructed (A-ON)", "No instruction\ngiven (A-OFF)"])
    ax.set_yticks([0.46, 1.46])
    ax.set_yticklabels([task_names[t] for t in reversed(tasks)])
    ax.set_title("Citation grounding, task by task: instructed vs. not\n"
                 "Each cell is one real Hydron run (n=4 total) - color is the actual outcome")
    ax.grid(False)
    ax.set_aspect("equal")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "3_grounding_on_vs_off.png"), dpi=160)
    plt.close(fig)

    # ---- Plot 4: grounding_class across the WHOLE campaign, original pilot vs expanded ----
    original_ids = {"S1", "S2", "S3", "S4", "S5", "GenC-ON", "GenC-OFF", "GenD-ON", "GenD-OFF"}
    orig_g = Counter(r["grounding_class"] for r in rows if r["run_id"] in original_ids)
    exp_g = Counter(r["grounding_class"] for r in rows if r["run_id"] not in original_ids)
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    x = range(len(gclass_order))
    w = 0.35
    ax.bar([i - w / 2 for i in x], [orig_g.get(g, 0) for g in gclass_order], width=w,
           label=f"Original pilot (n={sum(orig_g.values())})",
           color=[gclass_colors[g] for g in gclass_order], edgecolor="#333")
    ax.bar([i + w / 2 for i in x], [exp_g.get(g, 0) for g in gclass_order], width=w,
           label=f"Expanded campaign, in progress (n={sum(exp_g.values())})",
           color=[gclass_colors[g] for g in gclass_order], alpha=0.45, edgecolor="#333")
    ax.set_xticks(list(x))
    ax.set_xticklabels([gclass_labels[g] for g in gclass_order])
    ax.set_ylabel("Count of runs")
    ax.set_title("Diagnosis/citation quality: original pilot vs. expanded campaign\n"
                 "'confident_wrong' now also covers harness misdiagnoses, not just citations",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "4_pilot_vs_expanded.png"), dpi=160, bbox_inches="tight")
    plt.close(fig)

    # ---- Plot 5: per-target repair outcome (harness half only) ----
    def target_of(run_id):
        prefix = run_id.split("-")[0].rstrip("0123456789")
        return {
            "S": "usart_irq", "N": "miniblink", "T": "timer",
            "X": "button", "U": "usart (polling)",
        }.get(prefix, prefix)

    target_order = ["usart_irq", "miniblink", "timer", "button", "usart (polling)"]
    target_tier = defaultdict(Counter)
    target_n = Counter()
    for r in harness:
        t = target_of(r["run_id"])
        target_n[t] += 1
        target_tier[t][verification_tier(r)] += 1

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bottom = [0] * len(target_order)
    for tier in tier_order:
        vals = [target_tier[t].get(tier, 0) for t in target_order]
        ax.bar(target_order, vals, bottom=bottom, label=tier_labels[tier].split("\n")[0],
               color=tier_colors[tier])
        bottom = [b + v for b, v in zip(bottom, vals)]
    for i, t in enumerate(target_order):
        ax.annotate(f"n={target_n[t]}", (i, bottom[i] + 0.15), ha="center", fontsize=8.5)
    ax.set_ylabel("Count of runs")
    ax.set_title("Repair verification tier by firmware target\n"
                 "Same L0-L3 defect taxonomy applied to 5 different real example files")
    ax.set_ylim(0, max(target_n.values()) + 1.5)
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "5_by_target.png"), dpi=160)
    plt.close(fig)

    print(f"Wrote 5 plots to {OUT_DIR} from {n_total} logged runs "
          f"({n_harness} harness-half, {n_gen} generation-half).")


if __name__ == "__main__":
    main()
