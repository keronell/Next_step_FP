import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent

# ── Real data from raw JSON files ─────────────────────────────────────────────
SOURCE_TOTALS = {
    "jobspy":         1277,
    "remoteok":        114,
    "weworkremotely":   98,
    "jobicy":           38,
    "arbeitnow":        19,
    "remotive":         18,
    "themuse":          11,
    "workingnomads":     0,
}

SOURCE_FIELD = {
    "jobspy": {
        "Software Architecture": 263, "AI Engineering": 120,
        "Technical Writing": 103,     "Cyber Security": 95,
        "Data Science": 99,           "Full Stack Development": 100,
        "Data Analysis": 74,          "DevOps": 67,
        "Machine Learning": 65,       "UI / UX Design": 63,
        "Mobile Development": 55,     "Product Management": 51,
        "Frontend Development": 48,   "Backend Development": 34,
        "QA / Software Testing": 21,  "Game Development": 19,
    },
    "remoteok": {
        "UI / UX Design": 30, "Data Analysis": 27, "Cyber Security": 18,
        "QA / Software Testing": 16, "Technical Writing": 6, "Backend Development": 7,
        "Mobile Development": 4, "AI Engineering": 1, "Frontend Development": 1,
        "Full Stack Development": 2, "Product Management": 1, "Game Development": 1,
    },
    "weworkremotely": {
        "Product Management": 39, "UI / UX Design": 31, "DevOps": 22,
        "Full Stack Development": 4, "Frontend Development": 1, "Backend Development": 1,
    },
    "jobicy": {
        "Software Architecture": 4, "Backend Development": 7, "QA / Software Testing": 3,
        "AI Engineering": 2, "DevOps": 5, "Product Management": 3, "Full Stack Development": 2,
        "Frontend Development": 2, "Cyber Security": 4, "Machine Learning": 1,
        "Data Analysis": 3, "Data Science": 2,
    },
    "arbeitnow": {
        "QA / Software Testing": 4, "DevOps": 4, "Data Analysis": 3,
        "UI / UX Design": 2, "Frontend Development": 1, "Backend Development": 1,
        "Product Management": 1, "Full Stack Development": 1, "Machine Learning": 1,
        "AI Engineering": 1,
    },
    "remotive": {
        "Frontend Development": 2, "Data Analysis": 4, "QA / Software Testing": 2,
        "AI Engineering": 1, "Backend Development": 2, "Full Stack Development": 1,
        "Mobile Development": 1, "DevOps": 5,
    },
    "themuse": {
        "Data Science": 2, "UI / UX Design": 2, "Product Management": 7,
    },
    "workingnomads": {},
}

FIELDS = [
    "Software Architecture", "UI / UX Design", "AI Engineering", "Cyber Security",
    "Data Analysis", "Full Stack Development", "Technical Writing", "Data Science",
    "DevOps", "Product Management", "Machine Learning", "Mobile Development",
    "Frontend Development", "Backend Development", "QA / Software Testing", "Game Development",
]

SOURCES_ORDERED = [
    "jobspy", "remoteok", "weworkremotely", "jobicy",
    "arbeitnow", "remotive", "themuse", "workingnomads",
]

SOURCE_LABELS = {
    "jobspy":         "JobSpy (LinkedIn + Indeed)",
    "remoteok":       "RemoteOK",
    "weworkremotely": "We Work Remotely",
    "jobicy":         "Jobicy",
    "arbeitnow":      "Arbeitnow",
    "remotive":       "Remotive",
    "themuse":        "The Muse",
    "workingnomads":  "Working Nomads",
}

SOURCE_COLORS = {
    "jobspy":         "#4A7CC7",
    "remoteok":       "#E8843A",
    "weworkremotely": "#9B59B6",
    "jobicy":         "#3DA86A",
    "arbeitnow":      "#D94F3D",
    "remotive":       "#D4A017",
    "themuse":        "#1ABC9C",
    "workingnomads":  "#BDC3C7",
}

DARK     = "#1C1C1E"
MID_GRAY = "#8E8E93"
GRAY_BG  = "#F7F7F7"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
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
# Chart A — Jobs per Source
# ══════════════════════════════════════════════════════════════════════════════
fig_src, ax_src = plt.subplots(figsize=(9, 5.5))
fig_src.patch.set_facecolor("white")

src_names  = list(reversed(SOURCES_ORDERED))
src_counts = [SOURCE_TOTALS[s] for s in src_names]
src_colors = [SOURCE_COLORS[s] for s in src_names]

y_src = np.arange(len(src_names))
bars = ax_src.barh(y_src, src_counts, color=src_colors, height=0.6,
                   alpha=0.9, zorder=3, linewidth=0)

ax_src.set_facecolor(GRAY_BG)
ax_src.set_yticks(y_src)
ax_src.set_yticklabels([SOURCE_LABELS[s] for s in src_names], fontsize=10.5)
ax_src.set_xlabel("Jobs scraped", fontsize=11)
ax_src.set_title("Job Listings Collected per Source", fontsize=13,
                 fontweight="bold", pad=12)
ax_src.grid(axis="x", color="white", linewidth=1.4, zorder=2)
ax_src.spines["left"].set_color("#CCCCCC")
ax_src.spines["bottom"].set_color("#CCCCCC")

for bar, val in zip(bars, src_counts):
    if val > 0:
        ax_src.text(val + 12, bar.get_y() + bar.get_height() / 2,
                    str(val), va="center", ha="left",
                    fontsize=10, fontweight="bold", color=DARK)

total = sum(SOURCE_TOTALS.values())
fig_src.text(0.98, 0.02, f"Total: {total:,} job listings",
             ha="right", fontsize=10, fontweight="bold", color=DARK)
fig_src.text(0.5, -0.02,
             "8 sources scraped  ·  JobSpy (LinkedIn + Indeed) is the dominant contributor",
             ha="center", fontsize=9, color=MID_GRAY)

plt.tight_layout()
plt.savefig(OUT / "story7a_sources.png", dpi=180, bbox_inches="tight")
plt.close()
print("Saved: story7a_sources.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart B — Jobs per Field (stacked by source)
# ══════════════════════════════════════════════════════════════════════════════
fig_fld, ax_fld = plt.subplots(figsize=(11, 7))
fig_fld.patch.set_facecolor("white")

field_totals  = {f: sum(SOURCE_FIELD[s].get(f, 0) for s in SOURCES_ORDERED) for f in FIELDS}
fields_sorted = sorted(FIELDS, key=lambda f: field_totals[f])

y_fld = np.arange(len(fields_sorted))
lefts = np.zeros(len(fields_sorted))

for src in SOURCES_ORDERED:
    vals = np.array([SOURCE_FIELD[src].get(f, 0) for f in fields_sorted], dtype=float)
    ax_fld.barh(y_fld, vals, left=lefts, color=SOURCE_COLORS[src],
                height=0.65, alpha=0.9, zorder=3, linewidth=0)
    lefts += vals

ax_fld.set_facecolor(GRAY_BG)
ax_fld.set_yticks(y_fld)
ax_fld.set_yticklabels(fields_sorted, fontsize=10.5)
ax_fld.set_xlabel("Number of job listings", fontsize=11)
ax_fld.set_title("Job Listings per Career Field  (stacked by source)", fontsize=13,
                 fontweight="bold", pad=12)
ax_fld.grid(axis="x", color="white", linewidth=1.4, zorder=2)
ax_fld.spines["left"].set_color("#CCCCCC")
ax_fld.spines["bottom"].set_color("#CCCCCC")

for i, f in enumerate(fields_sorted):
    ax_fld.text(field_totals[f] + 3, i, str(field_totals[f]),
                va="center", ha="left", fontsize=10, fontweight="bold", color=DARK)

legend_patches = [
    mpatches.Patch(facecolor=SOURCE_COLORS[s], label=SOURCE_LABELS[s])
    for s in SOURCES_ORDERED if SOURCE_TOTALS[s] > 0
]
ax_fld.legend(
    handles=legend_patches,
    loc="lower right",
    fontsize=9,
    frameon=True,
    framealpha=0.93,
    edgecolor="#CCCCCC",
    ncol=2,
)

fig_fld.text(0.5, -0.02,
             "All 16 canonical career fields are represented  ·  1,575 total listings",
             ha="center", fontsize=9, color=MID_GRAY)

plt.tight_layout()
plt.savefig(OUT / "story7b_fields.png", dpi=180, bbox_inches="tight")
plt.close()
print("Saved: story7b_fields.png")
