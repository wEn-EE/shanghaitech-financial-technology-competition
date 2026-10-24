"""Read an experiment manifest and plot EQ_DEMO event-state diagnostics."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(manifest, output):
    path = Path(manifest)
    rows = [json.loads(s) for s in (path.parent / 'applied.jsonl').read_text().splitlines()]
    eq = [r for r in rows if r['symbol'] == 'EQ_DEMO']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    ax = axes[0]
    prices = [100.02, 100.04, 100.10]
    x = list(range(3))
    ax.bar([v-.2 for v in x], [50, 100, 0], width=.2, label='Before buy (seq 4)')
    ax.bar(x, [0, 30, 0], width=.2, label='After buy (seq 5)')
    ax.bar([v+.2 for v in x], [0, 0, 200], width=.2, label='After replenishment (seq 7)')
    ax.set(xticks=x, xticklabels=[f'{p:.2f}' for p in prices], xlabel='Ask price (CNY)',
           ylabel='Displayed quantity', title='SYNTHETIC ask liquidity changes')
    ax.legend(fontsize=8)
    ax = axes[1]
    seq = [r['seq'] for r in eq]
    spread = [r['quote']['spread_bps'] for r in eq]
    ax.plot(seq, spread, marker='o', color='#216b8a')
    ax.axvline(5, color='#a14b3c', linestyle='--', linewidth=.9)
    ax.text(5.15, 10, 'Buy order', fontsize=9)
    ax.scatter([6], [0], marker='x', s=70, color='#a14b3c')
    ax.annotate('Seq 6: one-sided\nspread is missing, not zero', xy=(6, 0), xytext=(6.4, 2.1),
                arrowprops={'arrowstyle': '->'}, fontsize=9)
    ax.set(xlabel='Applied sequence', ylabel='Quoted spread (bps)',
           title='Trade price alone misses liquidity changes', ylim=(-.7, 13))
    fig.suptitle('Chapter 9 | Deterministic toy venue; no real market data', fontsize=13)
    fig.savefig(output, dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main(*sys.argv[1:])
