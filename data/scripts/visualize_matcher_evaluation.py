"""Visualize the CURRENT matcher-rework evaluation (DEV-53).

Renders four static PNGs for the markdown report at
`docs/figures/matcher-evaluation/README.md`:

  1. fig1_label_distribution.png  — silver-label counts across all 16 careers,
     highlighting the game-dev floor (5 labels) and the frontend over-representation
     (47 labels) that compensating for the floor produced (DEV-52).
  2. fig2_model_comparison.png    — Gate-1 model comparison split into a GATING zone
     (calibration ECE + top-2 stability vs the reframed thresholds) and a
     DESCRIPTIVE-ONLY zone (panel-agreement metrics), visually separated.
  3. fig3_gate2_calibration.png   — Gate-2 finalist calibration (ECE raw vs
     temperature-scaled), marking the Gate-2 winner vs the deployable/shipped model.
  4. fig4_reliability_curve.png   — reliability diagram for the SHIPPED model
     (logistic_tuned, exported as data/models/matcher_logistic_v2.json, T=1.0).
  5. fig5_per_class_recall.png    — per-class top-1 recall for the shipped model,
     so weak classes are visible at a glance.

FRAMING (load-bearing): every figure states that its metrics measure AGREEMENT WITH
A SYNTHETIC LLM LABELING PANEL, not expert- or user-validated real-world accuracy.

Comparison tables (figs 1-3, 5 labels) are transcribed from the committed report
artifacts and cited inline — those reports are the authoritative published results
this ticket exists to visualize. The shipped model's reliability curve (fig 4) and
per-class recall (fig 5 bars) are RECOMPUTED from data via the exact pipeline code
(train_models.oof_logistic_tuned) and cross-checked against the report headline
numbers, because a curve needs per-bin granularity the report tables don't carry.

Run from repo root:  python data/scripts/visualize_matcher_evaluation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "data" / "scripts"
TRAINING_DIR = REPO_ROOT / "data" / "training"
OUT_DIR = REPO_ROOT / "docs" / "figures" / "matcher-evaluation"
sys.path.insert(0, str(SCRIPTS_DIR))

# ---------------------------------------------------------------- palette
# dataviz skill reference palette (light surface). Validated:
#   node validate_palette.js "#2a78d6,#008300,#e87ba4,#eda100" --mode light -> PASS
#   (contrast WARN on magenta/yellow -> relief rule: every bar carries a value label)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
# status (fixed, never themed)
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"
# categorical slots (fixed order)
BLUE, GREEN, MAGENTA, YELLOW = "#2a78d6", "#008300", "#e87ba4", "#eda100"
NEUTRAL_BAR = "#9ec5f4"  # blue-200: recessive fill for un-highlighted magnitude bars

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "sans-serif",
    # DejaVu Sans first: it's matplotlib's bundled font and reliably carries the
    # ★ ∝ ◂ ▲ ▼ ● glyphs used below (Segoe UI does not, → tofu boxes).
    "font.sans-serif": ["DejaVu Sans", "Segoe UI", "Arial"],
    "font.size": 10,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_2,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.titlecolor": INK,
    "grid.color": GRID,
    "axes.grid": False,
})

# Shared framing line — appears verbatim on every figure.
PANEL_CAVEAT = (
    "All metrics = AGREEMENT WITH A SYNTHETIC LLM LABELING PANEL (silver labels), "
    "NOT expert- or user-validated accuracy."
)


def _fig_caveat(fig, extra: str = "") -> None:
    """Stamp the load-bearing framing caption on the figure, in serious-tone ink."""
    txt = PANEL_CAVEAT + (("\n" + extra) if extra else "")
    fig.text(0.5, 0.012, txt, ha="center", va="bottom", fontsize=8.2,
             color=INK_2, style="italic", wrap=True)


def _style_ax(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(length=0)


# ================================================================ sourced data
# --- Silver-label counts, all 16 careers (data/training/dataset_metadata.json
#     "rows_by_label"; identical to silver_labels.parquet consensus top-1).
LABEL_COUNTS = {
    "frontend": 47, "devops": 18, "data-analyst": 17, "qa-engineer": 16,
    "data-science": 15, "machine-learning": 15, "backend": 15, "software-architect": 14,
    "fullstack": 13, "ux-designer": 12, "technical-writer": 11, "cyber-security": 11,
    "ai-engineer": 9, "mobile": 8, "product-manager": 6, "game-dev": 5,
}
N_ROWS = sum(LABEL_COUNTS.values())          # 232
N_CAREERS = len(LABEL_COUNTS)                # 16
UNIFORM = N_ROWS / N_CAREERS                 # 14.5
FLOOR = 5                                    # stratified-5-fold minimum (dataset_guards)

# --- Gate 1 comparison (data/training/baseline_evaluation.md). Stability for the
#     static scorers is 1.0 "by construction" (no training) — flagged, not gated.
GATE1_THRESH = {"max_ece": 0.10, "min_top2_stability": 0.60}
GATE1 = {
    #            top1   top2   top3   mrr    bal    ece    stability  learned/gated
    "formula":      dict(top1=.461, top2=.582, top3=.659, mrr=.611, bal=.493, ece=.162, stab=1.000, gated=False),
    "archetype_nn": dict(top1=.099, top2=.250, top3=.353, mrr=.284, bal=.102, ece=.133, stab=1.000, gated=False),
    "logistic":     dict(top1=.741, top2=.871, top3=.927, mrr=.838, bal=.694, ece=.034, stab=0.638, gated=True),
    "lightgbm":     dict(top1=.789, top2=.871, top3=.914, mrr=.858, bal=.744, ece=.128, stab=0.557, gated=True),
}

# --- Gate 2 finalist comparison (data/training/model_selection.md).
GATE2 = {
    "gbt_tuned":      dict(top1=.772, top2=.892, ece_raw=.135, ece_scaled=.047, T=1.65),
    "logistic_tuned": dict(top1=.724, top2=.849, ece_raw=.103, ece_scaled=.103, T=1.00),
    "small_nn":       dict(top1=.634, top2=.841, ece_raw=.130, ece_scaled=.101, T=0.90),
    "two_tower":      dict(top1=.634, top2=.746, ece_raw=.047, ece_scaled=.077, T=1.30),
}
GATE2_WINNER = "gbt_tuned"        # highest top-2, ECE-scaled tiebreak
GATE2_DEPLOYABLE = "logistic_tuned"  # only linear model has the exact-attribution serving path


# ================================================================ recompute shipped model
def recompute_shipped_oof():
    """Reproduce the SHIPPED model's pooled out-of-fold probabilities via the exact
    Phase-3 pipeline code (nested-CV tuned logistic == the deployable selection),
    then cross-check against model_selection.md before trusting the granular curve."""
    import train_models as tm

    df, X, y, _soft, careers, _arch, _meta = tm.load_data()
    oof, chosen_C = tm.oof_logistic_tuned(X, y)
    m = tm.rank_metrics(oof, y)
    ece_raw = tm.ece(oof, y)

    # Sanity gate: the reproduction must match the committed report (logistic_tuned:
    # top1 0.724, top2 0.849, ECE raw 0.103) or the figures would silently disagree.
    exp = GATE2["logistic_tuned"]
    for name, got, want in [("top1", m["top1"], exp["top1"]),
                            ("top2", m["top2"], exp["top2"]),
                            ("ece", ece_raw, exp["ece_raw"])]:
        if abs(got - want) > 0.02:
            raise SystemExit(
                f"Reproduced logistic_tuned {name}={got:.3f} disagrees with "
                f"model_selection.md {want:.3f} (>0.02) — pipeline/data drift; "
                "figures would misrepresent the shipped model.")
    print(f"shipped logistic_tuned reproduced: top1={m['top1']:.3f} "
          f"top2={m['top2']:.3f} ECE={ece_raw:.3f} (C per fold: {chosen_C})")
    return oof, y, careers, m, ece_raw


# ================================================================ figures
def fig1_label_distribution():
    careers = list(LABEL_COUNTS.keys())
    counts = [LABEL_COUNTS[c] for c in careers]
    colors = []
    for c in careers:
        if c == "game-dev":
            colors.append(CRITICAL)      # floor class
        elif c == "frontend":
            colors.append(WARNING)       # over-represented
        else:
            colors.append(NEUTRAL_BAR)

    fig, ax = plt.subplots(figsize=(11, 5.6))
    x = np.arange(len(careers))
    bars = ax.bar(x, counts, color=colors, width=0.72, zorder=3)
    for xi, v in zip(x, counts):
        ax.text(xi, v + 0.5, str(v), ha="center", va="bottom",
                fontsize=8.5, color=INK, fontweight="bold")

    ax.axhline(UNIFORM, color=INK_2, lw=1.3, ls=(0, (5, 3)), zorder=2)
    ax.text(len(careers) - 0.4, UNIFORM + 0.5, f"uniform share = {UNIFORM:.1f}",
            ha="right", va="bottom", fontsize=8.5, color=INK_2)
    ax.axhline(FLOOR, color=CRITICAL, lw=1.3, ls=(0, (2, 2)), zorder=2)
    ax.text(len(careers) - 0.4, FLOOR - 0.6, "5-label CV floor",
            ha="right", va="top", fontsize=8.5, color=CRITICAL)

    ax.set_xticks(x)
    ax.set_xticklabels(careers, rotation=45, ha="right", fontsize=8.5, color=INK_2)
    ax.set_ylabel("silver labels (consensus top-1)")
    ax.set_ylim(0, 52)
    ax.set_title("Silver-label distribution across 16 careers  —  imbalanced by construction",
                 fontsize=13, fontweight="bold", pad=10)
    _style_ax(ax)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, lw=0.8)

    legend = [
        Patch(facecolor=WARNING, label="frontend: over-represented (47 / 232 = 20%, >2x uniform)"),
        Patch(facecolor=CRITICAL, label="game-dev: at the statistical floor (5 labels)"),
        Patch(facecolor=NEUTRAL_BAR, label="other careers"),
    ]
    ax.legend(handles=legend, loc="upper right", frameon=False, fontsize=8.6,
              bbox_to_anchor=(1.0, 0.87))

    _fig_caveat(fig, "232 rows, labels panel-v2.1.0. Source: data/training/dataset_metadata.json. "
                     "The frontend spike is a side effect of back-filling the game-dev floor (DEV-52).")
    fig.subplots_adjust(bottom=0.30, top=0.90, left=0.07, right=0.98)
    fig.savefig(OUT_DIR / "fig1_label_distribution.png", dpi=150)
    plt.close(fig)


def fig2_model_comparison():
    """Gate-1 comparison: GATING zone (ECE + top-2 stability vs thresholds) visually
    separated from the DESCRIPTIVE-ONLY zone (panel-agreement metrics). The zone
    distinction is carried by (a) tinted axes backgrounds — green vs gray — and
    (b) bold banner labels, so it reads at a glance, not as a footnote."""
    scorers = ["formula", "archetype_nn", "logistic", "lightgbm"]
    xlab = ["formula\n(static)", "archetype_nn\n(static)", "logistic", "lightgbm"]
    x = np.arange(len(scorers))
    GATE_TINT, DESC_TINT = "#eef6ea", "#f0efe9"

    fig = plt.figure(figsize=(13, 9.5))
    # explicit axes rectangles [left, bottom, w, h] for precise banner/title spacing
    axA = fig.add_axes([0.075, 0.585, 0.40, 0.275])
    axB = fig.add_axes([0.565, 0.585, 0.40, 0.275])
    axC = fig.add_axes([0.075, 0.130, 0.89, 0.315])

    def gated_colors(ok):
        return [NEUTRAL_BAR if not GATE1[s]["gated"]
                else (GOOD if ok(GATE1[s]) else CRITICAL) for s in scorers]

    # ---- GATING zone --------------------------------------------------------
    fig.text(0.03, 0.905, "GATES THE DECISION", fontsize=13, fontweight="bold", color="#0a6b0a")
    fig.text(0.30, 0.907, "— calibration + top-2 recommendation stability vs the reframed thresholds",
             fontsize=10.5, color=INK_2)

    # A: ECE
    axA.set_facecolor(GATE_TINT)
    ece = [GATE1[s]["ece"] for s in scorers]
    axA.bar(x, ece, width=0.6, zorder=3, color=gated_colors(lambda g: g["ece"] <= GATE1_THRESH["max_ece"]))
    for xi, v in zip(x, ece):
        axA.text(xi, v + 0.004, f"{v:.3f}", ha="center", va="bottom", fontsize=9, color=INK, fontweight="bold")
    axA.axhline(GATE1_THRESH["max_ece"], color=CRITICAL, lw=1.5, ls=(0, (5, 3)), zorder=4)
    axA.set_xlim(-0.6, 3.9)
    axA.text(3.62, GATE1_THRESH["max_ece"], "pass\n≤ 0.10", ha="left", va="center",
             fontsize=8.6, color=CRITICAL, fontweight="bold")
    axA.set_title("Calibration error — ECE  (lower is better)", fontsize=11, pad=8)
    axA.set_xticks(x); axA.set_xticklabels(xlab, fontsize=9, color=INK_2)
    axA.set_ylim(0, 0.20); _style_ax(axA); axA.set_axisbelow(True); axA.yaxis.grid(True, color=GRID, lw=0.8)

    # B: top-2 stability
    axB.set_facecolor(GATE_TINT)
    stab = [GATE1[s]["stab"] for s in scorers]
    axB.bar(x, stab, width=0.6, zorder=3,
            color=gated_colors(lambda g: g["stab"] >= GATE1_THRESH["min_top2_stability"]))
    for xi, v, s in zip(x, stab, scorers):
        axB.text(xi, v + 0.02, f"{v:.3f}" + ("*" if not GATE1[s]["gated"] else ""),
                 ha="center", va="bottom", fontsize=9, color=INK, fontweight="bold")
    axB.axhline(GATE1_THRESH["min_top2_stability"], color=CRITICAL, lw=1.5, ls=(0, (5, 3)), zorder=4)
    axB.set_xlim(-0.6, 3.9)
    axB.text(3.62, GATE1_THRESH["min_top2_stability"], "pass\n≥ 0.60", ha="left", va="center",
             fontsize=8.6, color=CRITICAL, fontweight="bold")
    axB.set_title("Top-2 recommendation stability  (higher is better)", fontsize=11, pad=8)
    axB.set_xticks(x); axB.set_xticklabels(xlab, fontsize=9, color=INK_2)
    axB.set_ylim(0, 1.15); _style_ax(axB); axB.set_axisbelow(True); axB.yaxis.grid(True, color=GRID, lw=0.8)
    fig.text(0.565, 0.512, "* static scorers involve no training → stability 1.0 by construction (not gated)",
             fontsize=8, color=MUTED, style="italic")

    # ---- DESCRIPTIVE zone ---------------------------------------------------
    fig.text(0.03, 0.478, "DESCRIPTIVE ONLY", fontsize=13, fontweight="bold", color=INK_2)
    fig.text(0.245, 0.480, "— panel agreement; does NOT gate. A model 'wins' agreement "
                           "by learning the hand-authored bonus table.",
             fontsize=10.5, color=INK_2)

    axC.set_facecolor(DESC_TINT)
    metrics = ["top1", "top2", "top3", "mrr", "bal"]
    metric_lbl = ["top-1", "top-2", "top-3", "MRR", "balanced top-1"]
    cat = {"formula": NEUTRAL_BAR, "archetype_nn": MAGENTA, "logistic": BLUE, "lightgbm": GREEN}
    w = 0.2
    xm = np.arange(len(metrics))
    for i, s in enumerate(scorers):
        vals = [GATE1[s][m] for m in metrics]
        off = (i - 1.5) * w
        axC.bar(xm + off, vals, width=w * 0.92, color=cat[s], zorder=3, label=s)
        for xj, v in zip(xm + off, vals):
            axC.text(xj, v + 0.012, f"{v:.2f}", ha="center", va="bottom", fontsize=7.2, color=INK_2)
    axC.set_xticks(xm); axC.set_xticklabels(metric_lbl, fontsize=10, color=INK_2)
    axC.set_ylim(0, 1.08); axC.set_ylabel("agreement with panel")
    _style_ax(axC); axC.set_axisbelow(True); axC.yaxis.grid(True, color=GRID, lw=0.8)
    axC.legend(loc="upper left", frameon=False, fontsize=9, ncol=4, bbox_to_anchor=(0.0, 1.06))

    fig.suptitle("Model comparison — Gate 1 (reframed): calibration & stability decide; agreement is descriptive",
                 fontsize=14, fontweight="bold", y=0.965)
    _fig_caveat(fig, "Source: data/training/baseline_evaluation.md. Gate-1 QUALIFIER: logistic "
                     "(ECE 0.034 ≤ 0.10 AND stability 0.638 ≥ 0.60); lightgbm fails both.")
    fig.savefig(OUT_DIR / "fig2_model_comparison.png", dpi=150)
    plt.close(fig)


def fig3_gate2_calibration():
    models = ["gbt_tuned", "logistic_tuned", "small_nn", "two_tower"]
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    x = np.arange(len(models))
    w = 0.36
    raw = [GATE2[m]["ece_raw"] for m in models]
    scaled = [GATE2[m]["ece_scaled"] for m in models]
    ax.bar(x - w / 2, raw, width=w * 0.92, color=NEUTRAL_BAR, zorder=3, label="ECE raw")
    ax.bar(x + w / 2, scaled, width=w * 0.92, color=BLUE, zorder=3, label="ECE after temperature scaling")
    for xi, v in zip(x - w / 2, raw):
        ax.text(xi, v + 0.003, f"{v:.3f}", ha="center", va="bottom", fontsize=8, color=INK_2)
    for xi, v in zip(x + w / 2, scaled):
        ax.text(xi, v + 0.003, f"{v:.3f}", ha="center", va="bottom", fontsize=8, color=INK, fontweight="bold")

    ax.axhline(0.10, color=CRITICAL, lw=1.3, ls=(0, (5, 3)), zorder=4)
    ax.text(len(models) - 0.5, 0.104, "ECE ≤ 0.10", ha="right", va="bottom", fontsize=8.4, color=CRITICAL)

    labels = []
    for m in models:
        tag = ""
        if m == GATE2_WINNER:
            tag = "\n★ Gate-2 winner"
        if m == GATE2_DEPLOYABLE:
            tag += "\n● SHIPPED (deployable)"
        labels.append(m + tag)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.8, color=INK_2)
    ax.set_ylabel("expected calibration error")
    ax.set_ylim(0, 0.17)
    ax.set_title("Gate 2 — finalist calibration (ECE raw vs temperature-scaled)",
                 fontsize=13, fontweight="bold", pad=10)
    _style_ax(ax); ax.set_axisbelow(True); ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.legend(loc="upper center", frameon=False, fontsize=9, ncol=2)

    # explain the winner/deployable split
    ax.text(0.5, -0.30,
            "Winner picked on top-2 agreement (gbt_tuned 0.892), ECE-scaled tiebreak. "
            "SHIPPED = logistic_tuned: the only architecture with the linear exact-attribution "
            "serving path (explainability is a ship-blocker); its raw probs were best-calibrated (T=1.00).",
            transform=ax.transAxes, ha="center", va="top", fontsize=8, color=INK_2, wrap=True)

    _fig_caveat(fig, "Source: data/training/model_selection.md, gate2_winner.json. "
                     "Temperature fitted on the same OOF pool it's scored on — prototype-grade.")
    fig.subplots_adjust(bottom=0.34, top=0.90, left=0.08, right=0.97)
    fig.savefig(OUT_DIR / "fig3_gate2_calibration.png", dpi=150)
    plt.close(fig)


def fig4_reliability_curve(oof, y, ece_raw):
    """Reliability diagram for the shipped logistic_tuned (T=1.0 ⇒ shipped == raw)."""
    pred = oof.argmax(axis=1)
    conf = oof[np.arange(len(oof)), pred]
    correct = (pred == y).astype(float)
    n_bins = 10
    edges = np.linspace(0, 1, n_bins + 1)
    xs, ys, ns = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf >= lo) & ((conf < hi) if hi < 1.0 else (conf <= hi))
        if m.any():
            xs.append(conf[m].mean()); ys.append(correct[m].mean()); ns.append(int(m.sum()))

    fig, ax = plt.subplots(figsize=(7.6, 7.0))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1.4, ls=(0, (4, 3)), zorder=2,
            label="perfect calibration")
    # gap shading between the curve and the diagonal
    for xi, yi in zip(xs, ys):
        ax.plot([xi, xi], [xi, yi], color=SERIOUS, lw=1.0, alpha=0.6, zorder=3)
    sizes = 40 + 420 * (np.array(ns) / max(ns))
    ax.plot(xs, ys, color=BLUE, lw=2.0, zorder=4)
    ax.scatter(xs, ys, s=sizes, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=5,
               label="observed (marker size ∝ #profiles in bin)")
    for xi, yi, ni in zip(xs, ys, ns):
        ax.annotate(f"n={ni}", (xi, yi), textcoords="offset points", xytext=(8, -10),
                    fontsize=7.5, color=INK_2)

    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("mean predicted confidence (top-1 probability)")
    ax.set_ylabel("empirical agreement with panel label")
    ax.set_title("Reliability — SHIPPED model (logistic_tuned)", fontsize=13, fontweight="bold", pad=10)
    ax.text(0.04, 0.93, f"ECE = {ece_raw:.3f}   (T = 1.00, so shipped = raw)",
            transform=ax.transAxes, fontsize=10, color=INK, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", fc="#eef4fc", ec=BLUE, lw=1))
    _style_ax(ax); ax.set_axisbelow(True); ax.grid(True, color=GRID, lw=0.8)
    ax.legend(loc="lower right", frameon=False, fontsize=8.6)

    _fig_caveat(fig, "Recomputed via train_models.oof_logistic_tuned (5-fold OOF, seed 42), "
                     "cross-checked against model_selection.md. 'Agreement' here is with the synthetic panel.")
    fig.subplots_adjust(bottom=0.15, top=0.92, left=0.11, right=0.96)
    fig.savefig(OUT_DIR / "fig4_reliability_curve.png", dpi=150)
    plt.close(fig)


def fig5_per_class_recall(oof, y, careers):
    pred = oof.argmax(axis=1)
    recall, n_lab = {}, {}
    for c, name in enumerate(careers):
        m = y == c
        recall[name] = float((pred[m] == c).mean()) if m.any() else float("nan")
        n_lab[name] = int(m.sum())
    order = sorted(careers, key=lambda c: recall[c])  # weakest first (bottom)

    fig, ax = plt.subplots(figsize=(9.5, 7.2))
    yy = np.arange(len(order))
    vals = [recall[c] for c in order]
    colors = [CRITICAL if v < 0.5 else (WARNING if v < 0.7 else GOOD) for v in vals]
    ax.barh(yy, vals, color=colors, height=0.66, zorder=3)
    for yi, v in zip(yy, vals):
        ax.text(v + 0.015, yi, f"{v:.2f}", va="center", ha="left", fontsize=8.6,
                color=INK, fontweight="bold")

    ax.set_yticks(yy)
    ylabels = [f"{c}  (n={n_lab[c]}){'  ◂floor' if n_lab[c] <= FLOOR else ''}"
               for c in order]
    ax.set_yticklabels(ylabels, fontsize=9, color=INK_2)
    ax.set_xlim(0, 1.08); ax.set_xlabel("top-1 recall (agreement with panel label)")
    ax.set_title("Per-class recall — SHIPPED model (logistic_tuned)", fontsize=13,
                 fontweight="bold", pad=10)
    _style_ax(ax); ax.set_axisbelow(True); ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.spines["left"].set_visible(False)

    legend = [
        Patch(facecolor=CRITICAL, label="weak  (< 0.50)"),
        Patch(facecolor=WARNING, label="moderate  (0.50–0.69)"),
        Patch(facecolor=GOOD, label="strong  (≥ 0.70)"),
    ]
    ax.legend(handles=legend, loc="lower right", frameon=False, fontsize=8.6)

    _fig_caveat(fig, "Recomputed via train_models.oof_logistic_tuned (5-fold OOF, seed 42). "
                     "Weak classes (game-dev, software-architect, product-manager) are also the lowest-n — treat as low-confidence.")
    fig.subplots_adjust(bottom=0.13, top=0.92, left=0.20, right=0.96)
    fig.savefig(OUT_DIR / "fig5_per_class_recall.png", dpi=150)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig1_label_distribution()
    fig2_model_comparison()
    fig3_gate2_calibration()
    oof, y, careers, m, ece_raw = recompute_shipped_oof()
    fig4_reliability_curve(oof, y, ece_raw)
    fig5_per_class_recall(oof, y, careers)
    print(f"Wrote 5 figures to {OUT_DIR}")


if __name__ == "__main__":
    main()
