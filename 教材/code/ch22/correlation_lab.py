"""SYNTHETIC four-asset covariance lab; requires existing NumPy."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import numpy as np

ASSETS = ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"]


def covariance(x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("need at least two complete observations")
    y = x - x.mean(axis=0)
    return y.T @ y / (len(x) - 1)


def correlation(s):
    d = np.diag(s)
    if not np.isfinite(s).all() or np.any(d <= 0):
        raise ValueError("positive finite variances required")
    return s / np.sqrt(np.outer(d, d))


def shrink(s, alpha=0.2):
    if not 0 <= alpha <= 1:
        raise ValueError("alpha outside [0,1]")
    mu = np.trace(s) / len(s)
    if mu <= 0:
        raise ValueError("nonpositive average variance")
    return (1 - alpha) * s + alpha * mu * np.eye(len(s))


def dcc_step(q, z, target, a=0.03, b=0.94):
    if a < 0 or b < 0 or a + b >= 1:
        raise ValueError("invalid DCC parameters")
    new = (1 - a - b) * target + a * np.outer(z, z) + b * q
    return new, correlation(new)


def pairwise_example():
    x = np.array([[1, 1, np.nan], [-1, -1, np.nan],
                  [1, np.nan, 1], [-1, np.nan, -1],
                  [np.nan, 1, -1], [np.nan, -1, 1]])
    r = np.eye(3)
    for i in range(3):
        for j in range(i):
            keep = np.isfinite(x[:, i]) & np.isfinite(x[:, j])
            r[i, j] = r[j, i] = np.corrcoef(x[keep, i], x[keep, j])[0, 1]
    return x, r


def samples(n=240):
    rng = np.random.default_rng(20261112)
    rows = []
    for t in range(n):
        f = rng.normal()
        e = rng.normal(size=4)
        load = np.array([0.8, -0.5, 0.2, -0.2] if t < 140
                        else [0.85, 0.8, 0.65, 0.6])
        r = 0.01 * (load * f + np.sqrt(1 - load**2) * e)
        if t == 165:
            r[2] = np.nan
        rows.append(r)
    return np.array(rows)


def replay(x, train=60, window=40, decay=0.94):
    if len(x) < train or not 0 < decay < 1:
        raise ValueError("invalid history or decay")
    mean = x[:train].mean(axis=0)
    h = shrink(covariance(x[:train]))
    records = []
    last_update = train - 1
    for t in range(train, len(x)):
        forecast = h.copy()  # Available before observing return t.
        block = x[max(0, t-window+1):t+1]
        keep = np.isfinite(block).all(axis=1)
        ids = np.arange(max(0, t-window+1), t+1)[keep]
        s = covariance(block[keep]) if keep.sum() >= 10 else None
        if s is not None and np.all(np.diag(s) > 0):
            shrunk = shrink(s)
            r = correlation(shrunk)
            eig = np.linalg.eigvalsh(r)
            metrics = {"eq_bond": float(r[0, 1]),
                       "mean_abs_corr": float(np.abs(r[np.triu_indices(4, 1)]).mean()),
                       "largest_share": float(eig[-1] / 4),
                       "min_eigenvalue": float(np.linalg.eigvalsh(shrunk)[0])}
        else:
            metrics = None
        observed = bool(np.isfinite(x[t]).all())
        if observed:
            u = x[t] - mean
            h = decay * h + (1 - decay) * np.outer(u, u)
            last_update = t
        records.append({"t": t, "ready": t + 1,
                        "forecast_cov": forecast.tolist(),
                        "updated_cov": h.tolist(), "updated": observed,
                        "last_update": last_update, "complete_ids": ids.tolist(),
                        "n_complete": int(keep.sum()), "metrics": metrics})
    return {"mean": mean.tolist(), "records": records}


def run():
    x = samples()
    result = replay(x)
    raw, bad = pairwise_example()
    result.update({
        "data_kind": "SYNTHETIC", "seed": 20261112, "assets": ASSETS,
        "config": {"train": 60, "window": 40, "decay": 0.94, "alpha": 0.2},
        "input": [[None if not np.isfinite(v) else float(v) for v in row] for row in x],
        "invalid_pairwise_corr": bad.tolist(),
        "invalid_eigenvalues": np.linalg.eigvalsh(bad).tolist()
    })
    return result


def main():
    result = run()
    out = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    p = out / "results.json"
    p.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    manifest = {"numpy": np.__version__,
                "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "result_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out)
    print(json.dumps({str(t): result["records"][t-60]["metrics"] for t in (139, 165, 239)}))
    print(result["invalid_eigenvalues"])


if __name__ == "__main__":
    main()
