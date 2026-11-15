"""SYNTHETIC temporal validation; existing NumPy only."""
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
import numpy as np

HORIZON = 3

def data(n=240):
    rng = np.random.default_rng(20261115)
    f = 0.0
    states, rows = [], []
    for t in range(n + HORIZON):
        f = 0.85*f + rng.normal(scale=0.5)
        e = rng.normal(size=4)
        states.append(f)
        rows.append([f+0.1*e[0], f+0.15*e[1], e[2], e[3], 1.0])
    x = np.asarray(rows[:n])
    y = np.array([np.mean(states[t+1:t+HORIZON+1]) for t in range(n)])
    ready = np.arange(n) + HORIZON + 1
    return x, y, ready


def train_ids(ready, start):
    # Model fitting completes just before decision start (zero cost assumption).
    return np.flatnonzero((np.arange(len(ready)) < start) & (ready < start))


def fit(x, y, mode):
    if mode not in ('raw', 'pca1', 'pca2'):
        raise ValueError('unknown mode')
    if len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('invalid training data')
    mu = x.mean(axis=0)
    scale = x.std(axis=0, ddof=1)
    eligible = np.flatnonzero(scale > 1e-12)
    if len(eligible) < 2 or np.std(y) == 0:
        raise ValueError('need two variable features and variable target')
    scale = np.where(scale > 1e-12, scale, 1)
    z = (x-mu)/scale
    yc = y-y.mean()
    scores = np.abs(z[:, eligible].T @ yc) / (
        np.linalg.norm(z[:, eligible], axis=0)*np.linalg.norm(yc))
    order = np.argsort(-scores, kind='stable')[:2]
    selected = eligible[order]
    a = z[:, selected]
    _, singular, vt = np.linalg.svd(a, full_matrices=False)
    components = np.eye(2) if mode == 'raw' else vt[:int(mode[-1])].T
    transformed = a @ components
    ridge = 1.0  # Objective: summed squared error + ridge * ||beta||^2.
    beta = np.linalg.solve(transformed.T @ transformed + ridge*np.eye(transformed.shape[1]),
                           transformed.T @ yc)
    return {'mean': mu.tolist(), 'scale': scale.tolist(), 'selected': selected.tolist(),
            'components': components.tolist(), 'beta': beta.tolist(), 'intercept': float(y.mean()),
            'singular': singular.tolist(), 'mode': mode, 'ridge': ridge}


def predict(model, x):
    z = (x-np.array(model['mean']))/np.array(model['scale'])
    return z[:, model['selected']] @ np.array(model['components']) @ np.array(model['beta']) + model['intercept']


def select(x, y, ready):
    modes = ('raw', 'pca1', 'pca2')
    trials = []
    for mode in modes:
        folds = []
        for start in (80, 120, 160):
            tr = train_ids(ready, start)
            va = np.arange(start, start+20)
            m = fit(x[tr], y[tr], mode)
            loss = float(np.mean((predict(m, x[va])-y[va])**2))
            folds.append({'start': start, 'train_ids': tr.tolist(), 'validation_ids': va.tolist(),
                          'mse': loss, 'selected': m['selected']})
        trials.append({'mode': mode, 'mean_mse': float(np.mean([f['mse'] for f in folds])), 'folds': folds})
    winner = min(trials, key=lambda r: (r['mean_mse'], modes.index(r['mode'])))['mode']
    return winner, trials


def experiment(x, y, ready):
    winner, trials = select(x, y, ready)
    tr = train_ids(ready, 200)
    test = np.arange(200, len(y))
    model = fit(x[tr], y[tr], winner)
    pred = predict(model, x[test])
    baseline = float(y[tr].mean())
    return {'data_kind': 'SYNTHETIC', 'chosen': winner, 'trials': trials,
            'final_train_ids': tr.tolist(), 'test_ids': test.tolist(), 'model': model,
            'prediction': pred.tolist(), 'test_mse': float(np.mean((pred-y[test])**2)),
            'baseline_mse': float(np.mean((baseline-y[test])**2)),
            'x': x.tolist(), 'y': y.tolist(), 'label_ready': ready.tolist()}


def main():
    result = experiment(*data())
    out = Path(__file__).parent/'runs'/datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True)
    p = out/'results.json'
    p.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    manifest = {'numpy': np.__version__, 'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'result_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(out)
    print([(t['mode'], t['mean_mse']) for t in result['trials']])
    print(result['chosen'], result['test_mse'], result['baseline_mse'])
    print('train sizes', [len(f['train_ids']) for f in result['trials'][0]['folds']], len(result['final_train_ids']))

if __name__ == '__main__': main()
