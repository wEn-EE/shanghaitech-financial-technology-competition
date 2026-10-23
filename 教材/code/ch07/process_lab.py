"""Synthetic stochastic-process laboratory; no real market data or trading."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np


def transition_matrix(value):
    p = np.asarray(value, dtype=float)
    if p.ndim != 2 or p.shape[0] != p.shape[1] or not len(p):
        raise ValueError("P must be nonempty and square")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("probabilities must be finite and in [0, 1]")
    if not np.allclose(p.sum(axis=1), 1, rtol=0, atol=1e-12):
        raise ValueError("rows must sum to one; no silent normalization")
    return p.copy()


def stationary_two(value):
    p = transition_matrix(value)
    if p.shape != (2, 2):
        raise ValueError("this closed-form helper requires two states")
    a, b = p[0, 1], p[1, 0]
    if a + b == 0:
        raise ValueError("stationary distribution is not unique")
    return np.array([b, a]) / (a + b)


def simulate_chain(value, n, initial, rng):
    p = transition_matrix(value)
    if not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")
    if not isinstance(initial, int) or not 0 <= initial < len(p):
        raise ValueError("invalid initial state")
    states = np.empty(n, dtype=np.int64)
    states[0] = initial
    for t in range(1, n):
        states[t] = rng.choice(len(p), p=p[states[t-1]])
    return states


def fit_transitions(states, k=2, alpha=0.5):
    x = np.asarray(states)
    if x.ndim != 1 or len(x) < 2 or x.dtype.kind not in 'iu':
        raise ValueError("need at least two integer state labels")
    if not isinstance(k, int) or k < 1 or (x < 0).any() or (x >= k).any():
        raise ValueError("invalid state labels")
    if not np.isfinite(alpha) or alpha < 0:
        raise ValueError("alpha must be finite and nonnegative")
    counts = np.zeros((k, k), dtype=np.int64)
    np.add.at(counts, (x[:-1], x[1:]), 1)
    denominator = counts.sum(axis=1, keepdims=True) + k*alpha
    if (denominator == 0).any():
        raise ValueError("unobserved departure row; choose an explicit prior")
    return (counts + alpha) / denominator, counts


def conditional_nll(states, value):
    p = transition_matrix(value)
    x = np.asarray(states)
    if x.ndim != 1 or len(x) < 2 or x.dtype.kind not in 'iu':
        raise ValueError("need a sequence of integer labels")
    if (x < 0).any() or (x >= len(p)).any():
        raise ValueError("state index outside P")
    q = p[x[:-1], x[1:]]
    return float('inf') if (q == 0).any() else float(-np.log(q).mean())


def brownian_checks(rng, paths=4000, steps=1024):
    grids = (16, 64, 256, 1024)
    if not isinstance(paths, int) or paths < 2 or steps != 1024:
        raise ValueError("paths >= 2; this nested-grid experiment uses 1024 steps")
    totals = {n: [0.0, 0.0] for n in grids}
    w_end, left_values, right_values, gbm = [], [], [], []
    identity_error = 0.0
    for start in range(0, paths, 128):
        m = min(128, paths-start)
        dw = rng.normal(size=(m, steps)) / np.sqrt(steps)
        w = np.cumsum(dw, axis=1)
        left = np.sum((w-dw)*dw, axis=1)
        right = np.sum(w*dw, axis=1)
        end = w[:, -1]
        qv = np.sum(dw*dw, axis=1)
        identity_error = max(identity_error,
                             float(np.max(np.abs(2*left-(end*end-qv)))))
        w_end.extend(end.tolist())
        left_values.extend(left.tolist())
        right_values.extend(right.tolist())
        gbm.extend((100*np.exp((0.06-0.2**2/2)+0.2*end)).tolist())
        for n in grids:
            coarse = dw.reshape(m, n, steps//n).sum(axis=2)
            v = np.sum(coarse*coarse, axis=1)
            totals[n][0] += float(v.sum())
            totals[n][1] += float(np.sum((v-1)**2))
    return {
        'paths': paths, 'T_years': 1.0, 'nested_grids': grids,
        'qv': {str(n): {'mean': s/paths, 'rmse': np.sqrt(e/paths),
                        'theory_rmse': np.sqrt(2/n)}
               for n, (s, e) in totals.items()},
        'W_mean': float(np.mean(w_end)), 'W_variance': float(np.var(w_end, ddof=1)),
        'left_integral_mean': float(np.mean(left_values)),
        'right_sum_mean': float(np.mean(right_values)),
        'discrete_identity_max_error': identity_error,
        'gbm_terminal_mean': float(np.mean(gbm)),
        'gbm_theory_mean': float(100*np.exp(0.06)),
        'gbm_mean_mc_se': float(np.std(gbm, ddof=1)/np.sqrt(paths))}


def main(out=None):
    seed = 20261023
    children = np.random.SeedSequence(seed).spawn(5)
    rng = [np.random.Generator(np.random.PCG64(s)) for s in children]
    p = np.array([[0.96, 0.04], [0.20, 0.80]])
    n, split = 1600, 1000
    state = simulate_chain(p, n, 0, rng[0])
    fitted, counts = fit_transitions(state[:split], alpha=0.5)
    iid = (np.bincount(state[:split], minlength=2)+0.5)/(split+1)
    # In synthetic time, a label is available at tick+0.001.
    # Training ends at tick 999.001; model is released at tick 999.5.
    test = state[split-1:]  # include only the known boundary state
    means = np.array([[.0003,.0001,.0001,0],[-.001,.0002,.0004,.0001]])
    vols = np.array([[.008,.003,.006,.004],[.025,.007,.018,.012]])
    corr = np.full((4,4), .25)
    np.fill_diagonal(corr, 1)
    shocks = rng[1].normal(size=(n,4)) @ np.linalg.cholesky(corr).T
    log_returns = means[state] + vols[state]*shocks
    news = rng[2].poisson(np.array([2.,8.])[state])
    fixed_counts = rng[4].poisson(2.0, size=20000)
    waits = rng[4].exponential(scale=0.5, size=20000)
    summary = {
        'source': 'SYNTHETIC', 'seed': seed, 'bit_generator': 'PCG64',
        'spawn_keys': [list(s.spawn_key) for s in children],
        'n': n, 'split': split, 'train_last_tick': split-1,
        'label_delay_ticks': .001, 'model_release_tick': 999.5,
        'P_true': p.tolist(), 'pi_true': stationary_two(p).tolist(),
        'start_state': 0, 'alpha': .5, 'counts_train': counts.tolist(),
        'P_fit': fitted.tolist(), 'pi_fit': stationary_two(fitted).tolist(),
        'state_counts_all': np.bincount(state, minlength=2).tolist(),
        'five_step_from_train_last': np.linalg.matrix_power(fitted, 5)[state[split-1]].tolist(),
        'test_nll_true': conditional_nll(test,p),
        'test_nll_fit': conditional_nll(test,fitted),
        'test_nll_iid': conditional_nll(test,np.tile(iid,(2,1))),
        'means_daily_log_return': means.tolist(), 'vols_daily': vols.tolist(),
        'correlation': corr.tolist(), 'news_rate_per_tick': [2.,8.],
        'constant_poisson_count_mean': float(fixed_counts.mean()),
        'constant_poisson_count_variance': float(fixed_counts.var(ddof=1)),
        'exponential_wait_mean': float(waits.mean()),
        'brownian': brownian_checks(rng[3]),
        'python': platform.python_version(), 'numpy': np.__version__}
    dest = Path(out) if out else Path(__file__).parent/'runs'/datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    dest.mkdir(parents=True, exist_ok=False)
    csv_path = dest/'synthetic_market.csv'
    with csv_path.open('w',encoding='utf-8',newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['source','event_tick','available_tick','oracle_state','news_count',
                         'EQ_DEMO','BOND_DEMO','GOLD_DEMO','FX_DEMO'])
        for t in range(n):
            writer.writerow(['SYNTHETIC',t,t+.001,int(state[t]),int(news[t]),*log_returns[t]])
    summary['csv_sha256'] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    summary['program_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (dest/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(dest),**summary},ensure_ascii=False,indent=2,allow_nan=False))
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    main(parser.parse_args().out)
