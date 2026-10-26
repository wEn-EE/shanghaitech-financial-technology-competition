"""Render saved experiment outputs; no new simulation."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

run = Path(sys.argv[1])
result = json.loads((run/"results.json").read_text(encoding="utf-8"))
traces = json.loads((run/"traces.json").read_text(encoding="utf-8"))
d = result["dependence"]
fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
axes[0, 0].bar(["Calm", "Volatile", "Adjusted"],
               [d["calm_correlation"], d["volatile_correlation"], d["variance_adjusted_correlation"]],
               color=["#347aaf", "#d17d34", "#4b996a"])
axes[0, 0].set(title="Fixed linkage, different factor variance", ylabel="Correlation", ylim=(0, 1))
x = np.arange(2)
for offset, name, color in ((-.18, "gaussian", "#347aaf"), (.18, "mixture", "#d17d34")):
    axes[0, 1].bar(x+offset, [t["conditional_rate"] for t in d[name]["tails"]],
                   width=.36, label=name, color=color)
axes[0, 1].set(title="Similar correlation, different joint tails", ylabel="P(Y low | X low)",
               xticks=x, xticklabels=["5% cutoff", "1% cutoff"], ylim=(0, .55))
axes[0, 1].legend()
for scenario in traces:
    loss_c = [0] + [20-t["equity_after"][2] for t in scenario["trace"]]
    axes[1, 0].plot(range(len(loss_c)), loss_c, label=f"Impact {scenario['impact']:.2f}")
axes[1, 0].set(title="Institution C: no direct EQ exposure", xlabel="Auction round", ylabel="Cumulative equity loss")
axes[1, 0].legend()
direct = [sum(s["direct_loss"]) for s in traces]
extra = [max(0, sum(s["endogenous_loss"])) for s in traces]
axes[1, 1].bar(range(3), direct, label="External shock", color="#347aaf")
axes[1, 1].bar(range(3), extra, bottom=direct, label="Fire-sale feedback", color="#d17d34")
axes[1, 1].set(title="Same portfolios and shock; impact varies",
               xticks=range(3), xticklabels=["0", "0.05", "0.15"], xlabel="Impact parameter",
               ylabel="Total equity loss", ylim=(0, 12))
axes[1, 1].legend()
fig.suptitle("SYNTHETIC — dependence is not causal identification; stress is not a forecast")
target = Path(__file__).resolve().parents[2]/"images/ch15_contagion.png"
fig.savefig(target, dpi=150)
print(target)
