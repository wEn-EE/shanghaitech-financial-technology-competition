"""Plot saved results: python plot_timeseries.py MANIFEST OUTPUT_PNG."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(manifest_path, output_path):
    path = Path(manifest_path)
    report = json.loads(path.read_text(encoding='utf-8'))
    data = pd.read_csv(path.parent / 'synthetic.csv')
    predictions = pd.read_csv(path.parent / 'predictions.csv')
    pred = predictions[(predictions.asset == 'EQ_DEMO') &
                       (predictions.model == 'rolling_ar1')]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    ax = axes[0, 0]
    ax.plot(data.event_time, data.EQ_DEMO, linewidth=.7, color='#267594')
    for t, label in [(600, 'validation'), (800, 'test'), (1000, 'simulator break')]:
        ax.axvline(t, color='#9a4844', linestyle='--', linewidth=.8)
        ax.text(t + 8, .98, label, rotation=90, va='top', fontsize=8,
                transform=ax.get_xaxis_transform(), backgroundcolor='white')
    ax.set(title='SYNTHETIC equity log return', xlabel='Event index', ylabel='Return')
    ax = axes[0, 1]
    d = report['diagnostics_training_only']['EQ_DEMO']
    lag = np.arange(1, 13)
    ax.bar(lag - .18, d['acf'][1:], width=.36, label='ACF')
    ax.bar(lag + .18, d['pacf'][1:], width=.36, label='PACF')
    ax.axhline(0, color='black', linewidth=.6)
    ax.set(title='Training observations only', xlabel='Lag', ylabel='Correlation')
    ax.legend()
    ax = axes[1, 0]
    ax.fill_between(pred.t, pred.lower, pred.upper, color='#92bad0', alpha=.5, label='95% plug-in interval')
    ax.plot(pred.t, pred.actual, linewidth=.65, color='#244761', label='Observed')
    ax.axvline(1000, color='#9a4844', linestyle='--', linewidth=.8)
    ax.set(title='Rolling AR(1): interval adapts with delay', xlabel='Test event index', ylabel='Return')
    ax.legend(fontsize=8)
    ax = axes[1, 1]
    models = ['zero', 'fixed_ar1', 'rolling_ar1']
    positions = np.arange(3)
    for shift, part, label in [(-.18, 'first_200', 'Before break'), (.18, 'last_200', 'After break')]:
        y = [report['test_metrics']['EQ_DEMO'][m][part]['coverage95'] for m in models]
        ax.bar(positions + shift, y, width=.36, label=label)
    ax.axhline(.95, color='#9a4844', linestyle='--', label='Nominal 0.95')
    ax.set(xticks=positions, xticklabels=['Zero', 'Fixed AR(1)', 'Rolling AR(1)'],
           ylim=(0, 1.05), ylabel='Empirical coverage', title='Same 200 targets per period')
    ax.legend(fontsize=8, loc='lower left')
    fig.suptitle('Chapter 8 | One synthetic realization; no market-performance claim', fontsize=13)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main(*sys.argv[1:])
