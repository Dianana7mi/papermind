"""Plot actual pilot outputs only; unknown dollar costs remain unknown."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
output = ROOT / "evaluation/results"
result = json.loads((output / "pilot.json").read_text(encoding="utf-8"))
rows = result["retrieval"]
modes = ["dense", "bm25", "hybrid", "rerank"]
colors = ["#0072B2", "#E69F00", "#009E73", "#CC79A7"]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
)
profile = {
    mode: {
        "n": sum(r["mode"] == mode for r in rows),
        "missing_cost": sum(r["cpu_cost_usd"] is None for r in rows if r["mode"] == mode),
        "latency_ms": [r["latency_ms"] for r in rows if r["mode"] == mode],
    }
    for mode in modes
}
(output / "figure-data-profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")


def save(fig, name):
    fig.savefig(output / f"{name}.png", dpi=300)
    fig.savefig(output / f"{name}.svg")
    plt.close(fig)


fig, ax = plt.subplots(figsize=(7.2, 3.6), layout="constrained")
for i, (mode, color) in enumerate(zip(modes, colors, strict=True)):
    values = [r["ndcg@10"] for r in rows if r["mode"] == mode]
    ax.scatter(
        np.linspace(i - 0.12, i + 0.12, len(values)),
        values,
        s=23,
        color=color,
        alpha=0.7,
        marker=["o", "s", "^", "D"][i],
    )
    ax.plot([i - 0.18, i + 0.18], [np.mean(values)] * 2, color="black", lw=1.6)
ax.set(
    xticks=range(4),
    xticklabels=modes,
    ylabel="nDCG@10",
    ylim=(-0.04, 1.08),
    title=f"AWQ source-anchor retrieval pilot (n={len(rows) // 4} queries per mode)",
)
fig.supxlabel(
    "Points: individual queries; black line: mean. Agent labels, no human adjudication.", fontsize=7
)
save(fig, "retrieval-comparison")

fig, ax = plt.subplots(figsize=(7.2, 3.8), layout="constrained")
cases = list(dict.fromkeys(r["case"] for r in result["comparability_ablation"]))
matrix = np.array(
    [
        [
            next(
                r["correct"]
                for r in result["comparability_ablation"]
                if r["case"] == case and r["variant"] == variant
            )
            for case in cases
        ]
        for variant in ("without_comparability", "with_comparability")
    ]
)
ax.pcolormesh(
    np.arange(len(cases) + 1) - 0.5,
    np.arange(3) - 0.5,
    matrix,
    cmap="cividis",
    vmin=0,
    vmax=1,
    shading="flat",
)
ax.set_ylim(1.5, -0.5)
ax.set(
    xticks=range(len(cases)),
    xticklabels=[c.replace("_", "\n") for c in cases],
    yticks=[0, 1],
    yticklabels=["Always comparable\n(control)", "Comparability\nrules"],
    title="Synthetic condition-rule ablation (8 designed cases, not paper-level accuracy)",
)
for y in range(2):
    for x in range(len(cases)):
        ax.text(
            x,
            y,
            "PASS" if matrix[y, x] else "FAIL",
            ha="center",
            va="center",
            color="black" if matrix[y, x] else "white",
            fontsize=7,
        )
save(fig, "module-ablation")

fig, ax = plt.subplots(figsize=(7.2, 3.6), layout="constrained")
for i, (mode, color) in enumerate(zip(modes, colors, strict=True)):
    values = [r["latency_ms"] for r in rows if r["mode"] == mode]
    ax.scatter(
        np.linspace(i - 0.12, i + 0.12, len(values)),
        values,
        color=color,
        s=23,
        alpha=0.7,
        marker=["o", "s", "^", "D"][i],
    )
ax.set(
    xticks=range(4),
    xticklabels=modes,
    ylabel="Online retrieval latency (ms, log scale)",
    yscale="log",
    title="Pilot latency: individual calls; CPU; embedding index build excluded",
)
ax.text(
    0.02,
    0.96,
    "Cold model loads included where encountered; fixed run order; no significance claim.",
    transform=ax.transAxes,
    va="top",
    fontsize=7,
)
save(fig, "latency-comparison")

fig, ax = plt.subplots(figsize=(7.2, 3.4), layout="constrained")
for i, (_mode, color) in enumerate(zip(modes, colors, strict=True)):
    ax.scatter([i], [0], color=color, s=45, marker=["o", "s", "^", "D"][i])
ax.set(
    xticks=range(4),
    xticklabels=modes,
    ylabel="External generation API cost (USD)",
    ylim=(-0.01, 0.05),
    title="Retrieval pilot API generation cost: no generation calls",
)
ax.text(
    0.5,
    0.65,
    "All retrieval modes use local models.\nCPU hosting/electricity costs were not measured.\nLive RAG dollar cost is unknown: provider prices are not configured.",
    ha="center",
    va="center",
    transform=ax.transAxes,
    fontsize=8,
)
save(fig, "cost-comparison")
print("Four PNG/SVG figures written; cost and scope limitations embedded in each relevant figure.")

if (output / "agent-ablation.json").exists():
    agent = json.loads((output / "agent-ablation.json").read_text(encoding="utf-8"))["runs"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.2), layout="constrained", sharey=True)
    labels = ["A · Dense", "B · Hybrid", "C · Rerank", "D · Agentic", "PM A", "PM B", "PM Full"][: len(agent)]
    y = np.arange(len(agent))
    axes[0].scatter([r["latency_ms"] / 1000 for r in agent], y, color="#0072B2", marker="D", s=28)
    axes[0].set(
        yticks=y,
        yticklabels=labels,
        xlabel="End-to-end latency (s)",
        xlim=(0, None),
        title="One actual call per variant",
    )
    axes[0].invert_yaxis()
    axes[1].barh(y, [r["input_tokens"] for r in agent], color="#009E73", label="Input")
    axes[1].barh(
        y,
        [r["output_tokens"] for r in agent],
        left=[r["input_tokens"] for r in agent],
        color="#E69F00",
        label="Output",
    )
    axes[1].set(xlabel="Actual model tokens", title="Cost inputs; USD unknown")
    axes[1].legend(loc="upper right", fontsize=7)
    fig.suptitle("Seven-variant exploratory run: same public AWQ library and comparison question", fontsize=9)
    fig.supxlabel(
        "n=1 query; sequential/cold effects retained; no human quality gold. Dollar prices not configured.",
        fontsize=7,
    )
    save(fig, "agent-ablation")
