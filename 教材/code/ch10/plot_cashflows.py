"""Plot actual deterministic lab outputs with the existing Matplotlib install."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main(manifest, output):
    rows = json.loads((Path(manifest).parent / "results.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), constrained_layout=True)
    t=[0]+[r["t"] for r in rows["stock"]]
    raw=[p / rows["stock_prices"][0] * 100 for p in rows["stock_prices"]]
    total=[100.]+[r["total_index"] for r in rows["stock"]]
    axes[0].plot(t,raw,"o-",label="Raw price / initial price x 100")
    axes[0].plot(t,total,"o-",label="PIT total-return index")
    axes[0].annotate("Dividend",xy=(1,99),xytext=(.25,77),arrowprops={"arrowstyle":"->"})
    axes[0].annotate("2-for-1 split",xy=(2,49.5),xytext=(1.1,60),arrowprops={"arrowstyle":"->"})
    axes[0].set(xlabel="Synthetic event time",ylabel="Rebased value",title="A price drop need not be an economic loss",xticks=t,ylim=(42,112))
    axes[0].legend(fontsize=8,loc="upper right")
    shocks=rows["shocks"]
    for field,label in [("exact","Exact repricing"),("linear","Duration only"),("quadratic","Duration + convexity")]:
        axes[1].plot([r["shock_bp"] for r in shocks],[r[field] for r in shocks],"o-",label=label,markersize=3)
    axes[1].set(xlabel="Nominal annual YTM shock (bp)",ylabel="Price per 100 face",title="Fixed cash flows, same valuation time")
    axes[1].legend(fontsize=8)
    fig.suptitle("Chapter 10 | SYNTHETIC cash-flow and risk experiment")
    fig.savefig(output,dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main(*sys.argv[1:])
