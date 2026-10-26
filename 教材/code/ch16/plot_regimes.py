"""Plot saved ch16 artifacts; does not rerun or fit models."""
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

run = Path(sys.argv[1])
data = np.load(run/"samples.npz")
labels = json.loads((run/"labels.json").read_text(encoding="utf-8"))
cfg = json.loads((run/"configuration.json").read_text(encoding="utf-8"))
t = np.arange(len(data["truth"]))
fig, axs = plt.subplots(3, 1, figsize=(12, 10), constrained_layout=True, sharex=True)
axs[0].plot(t, data["truth"], color=".75", label="Synthetic hidden state", lw=2)
axs[0].plot(t, data["filtered"][:, 1], color="#125c99", label="Filtered: available through t")
axs[0].plot(t, data["smoothed"][:, 1], color="#b04a30", alpha=.65, ls="--", label="Smoothed: full history")
axs[0].set(ylabel="High-variance probability", title="SYNTHETIC / known-parameter mechanism experiment")
axs[0].legend(loc="upper right", ncol=1)
axs[1].plot(t, data["returns"][:, 0], color="#125c99", lw=.8)
axs[1].axvspan(310, 329, color="#bb7733", alpha=.15, label="EQ rolling feature unavailable")
axs[1].set(ylabel="EQ log return", title="Zero mean in both hidden regimes; variance differs")
axs[1].legend()
for j, (key, values) in enumerate([("trend", {"DOWN":0, "SIDEWAYS":1, "UP":2}),
                                  ("volatility", {"LOW":0, "HIGH":2}),
                                  ("liquidity", {"NORMAL":0, "TIGHT":2})]):
    arr = np.array([values.get(row[key], np.nan) for row in labels])
    axs[2].scatter([row["step"] for row in labels], np.full(len(arr), j),
                   c=arr, cmap="coolwarm", vmin=0, vmax=2, marker="|", s=100)
axs[2].set(yticks=[0, 1, 2], yticklabels=["Trend", "Volatility", "Liquidity"],
           xlabel="Synthetic observation step", title="Rules: blue = DOWN/LOW/NORMAL; red = UP/HIGH/TIGHT; grey = SIDEWAYS; blank = unavailable")
for ax in axs[:2]:
    ax.axvline(cfg["train"], color=".3", ls=":", lw=1)
for ax in axs:
    ax.grid(alpha=.15)
out = Path(__file__).parents[2]/"images"/"ch16_regimes.png"
fig.savefig(out, dpi=150)
print(out.resolve())
