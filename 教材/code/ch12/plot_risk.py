"""Plot one saved SYNTHETIC run; no model fitting."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("run", type=Path)
args = parser.parse_args()
report = json.loads((args.run/"results.json").read_text(encoding="utf-8"))
data = np.load(args.run/"daily.npz")
cfg = report["config"]
fig, axes = plt.subplots(1, 2, figsize=(13, 4.7), layout="constrained")
t = np.arange(cfg["train"], cfg["days"])
axes[0].plot(t, 100*np.sqrt(data["oracle_proxy_variance"]), color="black",
             linewidth=1.2, label="Known DGP conditional SD")
for i, name in enumerate(["Frozen", "Rolling 60", "EWMA 0.94"]):
    axes[0].plot(t, 100*np.sqrt(data["proxy_variance"][:, i]), label=name, alpha=.8)
axes[0].axvline(cfg["change"], color="gray", linestyle=":")
axes[0].set(xlabel="Synthetic day", ylabel="Daily SD of weighted log proxy (%)",
            title="Forecast before observing the target return")
axes[0].legend(fontsize=8)
rows = report["sampling"]
iv = cfg["daily_sigma"]**2
stride = [r["stride"] for r in rows]
axes[1].errorbar(stride, [r["noisy_mean"]/iv for r in rows],
                 yerr=[2*r["noisy_mc_se"]/iv for r in rows],
                 fmt="o-", label="Noisy RV mean +/- 2 Monte Carlo SE")
axes[1].plot(stride, [r["expected_noisy"]/iv for r in rows], "--",
             label="Theory: 1 + 2 n eta^2 / IV")
axes[1].plot(stride, [r["clean_mean"]/iv for r in rows], "s-",
             label="Latent clean RV mean")
axes[1].axhline(1, color="gray", linewidth=.8)
axes[1].set(xscale="log", yscale="log", xlabel="Sampling stride (base grid units)",
            ylabel="Mean realized variance / true IV",
            title="Same 200 paths; grid gets coarser to the right")
axes[1].legend(fontsize=8)
for ax in axes:
    ax.grid(alpha=.2)
fig.suptitle("SYNTHETIC: time-varying risk versus measurement noise")
out = Path(__file__).resolve().parents[2]/"images/ch12_risk.png"
fig.savefig(out, dpi=160)
print(out)
