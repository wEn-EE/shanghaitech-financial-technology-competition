"""Plot saved Chapter 6 results; do not rerun or select a favorable simulation."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("manifest", type=Path)
args = parser.parse_args()
report = json.loads(args.manifest.read_text(encoding="utf-8"))
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
names = ["iid_t", "oracle_z", "hac_z", "block_percentile"]
labels = ["IID t", "Known-model z", "HAC z", "Block bootstrap"]
for offset, rho, color in [(-.17, "0.0", "#247BA0"), (.17, "0.6", "#D97738")]:
    records = [report["coverage"][rho][name] for name in names]
    axes[0].bar(np.arange(4) + offset, [r["coverage"] for r in records], width=.32,
                yerr=[2 * r["mc_se"] for r in records], capsize=3,
                label=f"rho = {rho}", color=color)
axes[0].axhline(.95, color="#293241", ls="--", label="Nominal 95%")
axes[0].set(xticks=np.arange(4), xticklabels=labels, ylim=(0, 1.05),
            ylabel="Coverage probability", title="Synthetic mean intervals (error bars: 2 MC SE)")
axes[0].tick_params(axis="x", labelsize=9)
axes[0].legend(fontsize=8, loc="lower left")
rare = report["binomial_exact_coverage_n100_p001"]
axes[1].bar(list(rare), list(rare.values()), color=["#D97738", "#247BA0", "#38846D"])
axes[1].axhline(.95, color="#293241", ls="--")
for i, value in enumerate(rare.values()):
    axes[1].text(i, value + .015, f"{value:.4f}", ha="center")
axes[1].set(ylim=(0, 1.08), ylabel="Exact finite-sample coverage",
            title="Binomial model: n = 100, p = 0.01")
fig.suptitle("SYNTHETIC experiments: coverage is a property to check", fontsize=13)
out = Path(__file__).parents[2] / "images" / "ch06_inference.png"
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=170)
plt.close(fig)
print(out)
