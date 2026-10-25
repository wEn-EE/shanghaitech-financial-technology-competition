"""Read one saved synthetic run; plot ledger error and European call values."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from derivatives_lab import bs_call

parser = argparse.ArgumentParser()
parser.add_argument("run", type=Path)
args = parser.parse_args()
results = json.loads((args.run / "results.json").read_text(encoding="utf-8"))
inputs = json.loads((args.run / "inputs.json").read_text(encoding="utf-8"))
if results["label"] != "SYNTHETIC":
    raise ValueError("not a teaching run")
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
times = [x["event_at"] for x in results["ledger"]]
axes[0].plot(times, results["naive_splice_pnl"], "s--", label="Wrong splice P&L")
axes[0].plot(times, [x["equity"] - inputs["capital"] for x in results["ledger"]],
             "o-", label="Contract ledger, after roll fees")
axes[0].axvline(1, color="gray", alpha=.5, linestyle=":")
axes[0].set(xlabel="Synthetic event time", ylabel="Cumulative P&L (DEMO_CCY)",
            title="Roll after marking the old contract")
axes[0].legend()
spots = list(range(50, 151))
option = inputs["option"]
values = [bs_call(**(option | {"spot": float(s)})) for s in spots]
axes[1].plot(spots, values, label="BS model value: T=1, r=5%, sigma=20%")
axes[1].plot(spots, [max(s - option["strike"], 0) for s in spots], "--",
             label="Immediate intrinsic value max(S-K, 0)")
axes[1].set(xlabel="Underlying spot (DEMO_CCY)", ylabel="Call value (DEMO_CCY)",
            title="European call, strike=100, no dividends")
axes[1].legend(fontsize=8)
for ax in axes:
    ax.grid(alpha=.2)
fig.suptitle("SYNTHETIC teaching data and model calculations")
out = Path(__file__).resolve().parents[2] / "images" / "ch11_derivatives.png"
fig.savefig(out, dpi=160)
print(out)
