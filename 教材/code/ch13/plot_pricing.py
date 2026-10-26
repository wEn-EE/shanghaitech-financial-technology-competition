"""Plot saved SYNTHETIC results, without rerunning or selecting models."""
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

run = Path(sys.argv[1])
r = json.loads((run/'results.json').read_text(encoding='utf-8'))
d = np.load(run/'inputs_outputs.npz')
t = np.arange(r['config']['train'], r['config']['days'])
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
ax[0].plot(t, d['true_beta'][t, 0, 0], color='black', label='DGP truth (audit only)')
ax[0].plot(t, d['estimated_beta'][:, 1, 1, 0], label='Frozen two-factor')
ax[0].plot(t, d['estimated_beta'][:, 2, 1, 0], label='Rolling 240, pre-period fit')
ax[0].axvline(r['config']['change'], color='gray', linestyle=':')
ax[0].set(xlabel='Synthetic period', ylabel='EQ market loading',
          title='Exposure adapts after a change')
ax[0].legend(fontsize=8)
models = r['models']
x = np.arange(3)
v = r['metrics']['all']
ax[1].bar(x-.18, [100*v[m]['attribution_rmse'][0] for m in models], .36,
          label='Ex-post attribution')
ax[1].bar(x+.18, [100*v[m]['forecast_rmse'][0] for m in models], .36,
          label='Ex-ante mean forecast')
ax[1].set_xticks(x, ['Market frozen', 'Two frozen', 'Two rolling'])
ax[1].set(ylabel='EQ RMSE (percentage points)', title='Different information, different tasks')
ax[1].set_ylim(0, 1.9)
ax[1].legend(fontsize=8)
for a in ax:
    a.grid(alpha=.2, axis='y')
fig.suptitle('SYNTHETIC — not real-market performance')
out = Path(__file__).resolve().parents[2]/'images'/'ch13_pricing.png'
fig.savefig(out, dpi=170)
print(out)
