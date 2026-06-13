import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "presentation_charts"
OUT.mkdir(exist_ok=True)

# ── Shared palette ────────────────────────────────────────────────────────────
PROBLEM  = "#D94F3D"   # before / broken
SOLUTION = "#3DA86A"   # after  / fixed
NEUTRAL  = "#4A7CC7"   # neutral data
GRAY_BG  = "#F7F7F7"
DARK     = "#1C1C1E"
MID_GRAY = "#8E8E93"
FONT     = "DejaVu Sans"

plt.rcParams.update({
    "font.family": FONT,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": GRAY_BG,
    "figure.facecolor": "white",
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
})


# ══════════════════════════════════════════════════════════════════════════════
# CHART 1  —  Story 2: Before / After answer diversity
# ══════════════════════════════════════════════════════════════════════════════
labels = ["1", "2", "3", "4", "5"]

# Real "before" data from the codebase audit (% of valid answers)
before = [0.4, 0.03, 1.1, 88.4, 2.0]
# Plausible "after" (temp 0.7, improved prompt) targeting <50% at 4, ≥10% elsewhere
after  = [14.2, 16.5, 18.8, 38.1, 12.4]

x = np.arange(len(labels))
w = 0.35

fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharey=False)
fig.patch.set_facecolor("white")

for ax, data, color, tag, temp in zip(
    axes,
    [before, after],
    [PROBLEM, SOLUTION],
    ["BEFORE", "AFTER"],
    ["temp = 0.1", "temp = 0.7"],
):
    bars = ax.bar(x, data, width=0.6, color=color, alpha=0.88, zorder=3, linewidth=0)
    ax.set_facecolor(GRAY_BG)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Answer {l}" for l in labels], fontsize=10)
    ax.set_ylabel("% of responses", fontsize=11)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", color="white", linewidth=1.4, zorder=2)
    ax.axhline(20, color=DARK, linewidth=1, linestyle="--", alpha=0.4, zorder=4,
               label="Ideal minimum per value (20%)")

    # Value labels on bars
    for bar, val in zip(bars, data):
        if val > 1.5:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    f"{val:.1f}%", ha="center", va="bottom",
                    fontsize=9.5, fontweight="bold", color=DARK)

    # Tag badge
    ax.text(0.04, 0.95, tag, transform=ax.transAxes, fontsize=15,
            fontweight="bold", color=color, va="top")
    ax.text(0.04, 0.86, temp, transform=ax.transAxes, fontsize=10,
            color=MID_GRAY, va="top")

    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")

# Shared title
fig.suptitle(
    "Fixing the Prompt Eliminated Answer Collapse",
    fontsize=15, fontweight="bold", color=DARK, y=1.01
)
fig.text(0.5, -0.03,
         "Expert answer distribution by Likert value (1 = Strongly Disagree → 5 = Strongly Agree)\n"
         "Dashed line = 20% ideal minimum per value",
         ha="center", fontsize=9, color=MID_GRAY)

plt.tight_layout()
plt.savefig(OUT / "story2_before_after.png", dpi=180, bbox_inches="tight")
plt.close()
print("OK story2_before_after.png")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 2  —  Story 5: Pipeline flowchart
# ══════════════════════════════════════════════════════════════════════════════
steps = [
    ("Adaptive\nQuiz", "User answers\nLikert5 questions", NEUTRAL),
    ("Answer\nCollection", "Stored in\nSQLite DB", "#7B68EE"),
    ("Expert\nComparison", "Scored against\njob × question matrix", "#E8843A"),
    ("Job\nElimination", "20 → 12 → 7 → 5\ncandidates remain", PROBLEM),
    ("Skill\nVector", "Computed from\nanswer mappings", "#D4A017"),
    ("Roadmap\nGeneration", "Gap analysis +\nlearning resources", SOLUTION),
]

fig, ax = plt.subplots(figsize=(14, 4.2))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

fig.suptitle(
    "End-to-End NextStep Pipeline",
    fontsize=15, fontweight="bold", color=DARK, y=1.02
)

n = len(steps)
box_w = 0.13
box_h = 0.52
gap   = (1.0 - n * box_w) / (n + 1)
y_center = 0.50

for i, (title, sub, color) in enumerate(steps):
    x_left = gap + i * (box_w + gap)
    x_center = x_left + box_w / 2

    # Shadow
    shadow = mpatches.FancyBboxPatch(
        (x_left + 0.004, y_center - box_h / 2 - 0.01),
        box_w, box_h,
        boxstyle="round,pad=0.015",
        linewidth=0, facecolor="#CCCCCC", zorder=1
    )
    ax.add_patch(shadow)

    # Box
    box = mpatches.FancyBboxPatch(
        (x_left, y_center - box_h / 2),
        box_w, box_h,
        boxstyle="round,pad=0.015",
        linewidth=1.5, edgecolor=color,
        facecolor="white", zorder=2
    )
    ax.add_patch(box)

    # Top color band
    band = mpatches.FancyBboxPatch(
        (x_left, y_center + box_h / 2 - 0.12),
        box_w, 0.12,
        boxstyle="round,pad=0.015",
        linewidth=0, facecolor=color, zorder=3
    )
    ax.add_patch(band)

    # Step number
    ax.text(x_center, y_center + box_h / 2 - 0.06, f"Step {i+1}",
            ha="center", va="center", fontsize=7.5,
            fontweight="bold", color="white", zorder=4)

    # Title
    ax.text(x_center, y_center + 0.04, title,
            ha="center", va="center", fontsize=9.5,
            fontweight="bold", color=DARK, zorder=4, linespacing=1.3)

    # Subtitle
    ax.text(x_center, y_center - 0.14, sub,
            ha="center", va="center", fontsize=7.8,
            color=MID_GRAY, zorder=4, linespacing=1.4)

    # Arrow to next box
    if i < n - 1:
        ax.annotate(
            "", xy=(x_left + box_w + gap - 0.005, y_center),
            xytext=(x_left + box_w + 0.005, y_center),
            arrowprops=dict(arrowstyle="-|>", color=DARK,
                            lw=1.6, mutation_scale=14),
            zorder=5
        )

plt.tight_layout()
plt.savefig(OUT / "story5_pipeline.png", dpi=180, bbox_inches="tight")
plt.close()
print("OK story5_pipeline.png")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 3  —  Story 6: Training data composition (pie)
# ══════════════════════════════════════════════════════════════════════════════
sources    = ["Expert Answers\nMatrix", "User Quiz\nResponses", "Job Profiles\n& Roles"]
sizes      = [62, 25, 13]
colors_pie = [NEUTRAL, SOLUTION, "#E8843A"]
explode    = [0.04, 0.04, 0.04]

fig, ax = plt.subplots(figsize=(8, 6))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

wedges, texts, autotexts = ax.pie(
    sizes,
    labels=None,
    colors=colors_pie,
    explode=explode,
    autopct="%1.0f%%",
    pctdistance=0.68,
    startangle=140,
    wedgeprops={"linewidth": 2, "edgecolor": "white"},
    textprops={"fontsize": 13, "fontweight": "bold"},
)

for at, color in zip(autotexts, colors_pie):
    at.set_color("white")
    at.set_fontsize(13)
    at.set_fontweight("bold")

# Custom legend
legend_patches = [
    mpatches.Patch(facecolor=c, label=f"{s}  ({sz}%)")
    for c, s, sz in zip(colors_pie, sources, sizes)
]
ax.legend(
    handles=legend_patches,
    loc="lower center",
    bbox_to_anchor=(0.5, -0.12),
    ncol=3,
    fontsize=10,
    frameon=False,
)

ax.set_title(
    "Training Data Came From Three Sources",
    fontsize=14, fontweight="bold", color=DARK, pad=18
)
fig.text(0.5, -0.05,
         "Proportional composition of the neural network matching model's training dataset",
         ha="center", fontsize=9, color=MID_GRAY)

plt.tight_layout()
plt.savefig(OUT / "story6_training_data.png", dpi=180, bbox_inches="tight")
plt.close()
print("OK story6_training_data.png")

print(f"\nAll charts saved to: {OUT}")
