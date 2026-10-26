"""Plot saved SYNTHETIC inputs and snapshots; no fresh simulation."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

run = Path(sys.argv[1])
inputs = json.loads((run / "inputs.json").read_text(encoding="utf-8"))
snapshots = json.loads((run / "snapshots.json").read_text(encoding="utf-8"))
fig, axes = plt.subplots(3, 1, figsize=(10, 8), constrained_layout=True)
for j, (series, threshold) in enumerate((("GROWTH_DEMO", 4), ("INFLATION_DEMO", 2))):
    for version, label, style in ((1, "First release", "-o"), (2, "Revision (+90 days)", "--")):
        rows = sorted((e for e in inputs["releases"] if e["series"] == series and e["version"] == version),
                      key=lambda e: e["period_end"])
        axes[j].plot(range(1, 37), [e["value"] for e in rows], style, label=label, markersize=3)
    axes[j].axhline(threshold, color="gray", linewidth=1)
    axes[j].set(title=series + " | grouped by observation month, NOT availability", ylabel="YoY (%)")
    axes[j].legend(loc="upper right", fontsize=8)
    axes[j].grid(alpha=.2)
different = [int(s["pit_state"] != s["LEAKY_DIAGNOSTIC_state"]) for s in snapshots]
axes[2].bar(range(1, 37), different, color="#b64e44")
axes[2].set(title=f"Future revisions alter {sum(different)}/36 state snapshots (diagnostic only)",
            xlabel="Observation month index / following decision index", ylabel="State differs", yticks=[0, 1])
fig.suptitle("SYNTHETIC macro vintages — revised values are unavailable at early decisions", fontsize=12)
target = Path(__file__).resolve().parents[2] / "images" / "ch14_macro.png"
fig.savefig(target, dpi=150)
print(target)
