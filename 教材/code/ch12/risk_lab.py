"""SYNTHETIC returns, conditional risk, stale quotes and noisy realized variance."""
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ASSETS = ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"]
CONFIG = {"seed": 20261026, "days": 1200, "burn": 500, "train": 600,
          "change": 1000, "window": 60, "decay": .94,
          "weights": [.4, .3, .15, .15], "intraday_paths": 200,
          "intraday_steps": 3900, "daily_sigma": .01, "noise_sigma": .0005,
          "strides": [1, 5, 10, 30, 60, 130, 390]}


def matrix(x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("finite 2D panel with >=2 complete rows required")
    return x


def covariance(x):
    x = matrix(x)
    centered = x - x.mean(axis=0)
    return centered.T @ centered / (len(x) - 1)


def second_moment(x):
    x = matrix(x)
    return x.T @ x / len(x)


def correlation(cov):
    cov = np.asarray(cov, dtype=float)
    if (cov.ndim != 2 or cov.shape[0] != cov.shape[1]
            or not np.isfinite(cov).all() or not np.allclose(cov, cov.T)
            or np.linalg.eigvalsh(cov).min() < -1e-12
            or np.any(np.diag(cov) <= 0)):
        raise ValueError("symmetric PSD matrix with positive variances required")
    sd = np.sqrt(np.diag(cov))
    return cov / np.outer(sd, sd)


def aggregate_log_variance(gamma, horizon):
    gamma = np.asarray(gamma, dtype=float)
    if (isinstance(horizon, bool) or not isinstance(horizon, int)
            or horizon < 1 or gamma.ndim != 1 or len(gamma) < horizon
            or not np.isfinite(gamma[:horizon]).all()):
        raise ValueError("provide autocovariances 0,...,horizon-1")
    h = np.arange(1, horizon)
    return float(horizon * gamma[0] + 2 * np.dot(horizon-h, gamma[1:horizon]))


def describe(x):
    x = matrix(x)
    z = x - x.mean(axis=0)
    m2 = (z*z).mean(axis=0)
    if np.any(m2 == 0):
        raise ValueError("standardized moments undefined for constant columns")
    return {"mean": x.mean(axis=0).tolist(),
            "sd_ddof1": np.sqrt(np.diag(covariance(x))).tolist(),
            "skew_moment": ((z**3).mean(axis=0)/m2**1.5).tolist(),
            "excess_moment": ((z**4).mean(axis=0)/m2**2-3).tolist()}


def generate_daily(rng):
    h, previous = .0001, 0.0
    returns, truth = [], []
    idio = np.array([.004, .002, .006, .003])
    for t in range(-CONFIG["burn"], CONFIG["days"]):
        stressed = t >= CONFIG["change"]
        omega = 8e-6 if stressed else 2e-6
        h = omega + .08 * previous**2 + .90 * h
        factor = np.sqrt(h) * rng.normal()
        loading = np.array([1., .5 if stressed else -.3, .2, -.2])
        x = loading * factor + idio * rng.normal(size=4)
        if t >= 0:
            returns.append(x)
            truth.append(h * np.outer(loading, loading) + np.diag(idio**2))
        previous = factor
    return np.array(returns), np.array(truth)


def forecasts(x, start=600, window=60, decay=.94, available=None):
    """Emit covariance proxies before consuming the target observation."""
    x = matrix(x)
    if not 2 <= window <= start < len(x) or not 0 < decay < 1:
        raise ValueError("invalid split/window/decay")
    available = np.arange(len(x)) + .1 if available is None else np.asarray(available)
    if available.shape != (len(x),) or not np.isfinite(available).all():
        raise ValueError("invalid arrival times")
    frozen = second_moment(x[:start])
    state = frozen.copy()
    predictions, protocol = [], []
    for t in range(start, len(x)):
        decision = t - .2
        if np.max(available[:t]) > decision:
            raise ValueError("history contains an observation not yet available")
        rolling = second_moment(x[t-window:t])
        predictions.append(np.stack([frozen, rolling, state.copy()]))
        protocol.append([t, t-1, float(np.max(available[:t])), decision])
        # This update is used only for the NEXT prediction.
        state = decay * state + (1-decay) * np.outer(x[t], x[t])
    return np.array(predictions), np.array(protocol)


def evaluate(predicted, x, truth, start):
    weights = np.array(CONFIG["weights"])
    variance = np.einsum("i,tmij,j->tm", weights, predicted, weights)
    actual_square = (x[start:] @ weights)**2
    oracle = np.einsum("i,tij,j->t", weights, truth[start:], weights)
    if np.any(variance <= 0):
        raise ValueError("positive forecast variance required")
    result = {}
    for name, mask in [("all", np.arange(start, len(x)) >= start),
                       ("before_change", np.arange(start, len(x)) < CONFIG["change"]),
                       ("after_change", np.arange(start, len(x)) >= CONFIG["change"])]:
        result[name] = {
            model: {"qlike": float(np.mean(np.log(variance[mask, i]) +
                                          actual_square[mask]/variance[mask, i])),
                    "oracle_variance_mae": float(np.mean(abs(variance[mask, i]-oracle[mask])))}
            for i, model in enumerate(["frozen", "rolling60", "ewma94"])}
    return result, variance, oracle


def sampling_experiment(rng):
    # Same latent paths for all sampling grids; independent additive level noise.
    n, paths = CONFIG["intraday_steps"], CONFIG["intraday_paths"]
    sigma, eta = CONFIG["daily_sigma"], CONFIG["noise_sigma"]
    latent = np.column_stack([np.zeros(paths),
                              np.cumsum(rng.normal(0, sigma/np.sqrt(n), (paths, n)), axis=1)])
    observed = latent + rng.normal(0, eta, latent.shape)
    records = []
    for stride in CONFIG["strides"]:
        if n % stride:
            raise ValueError("grid must include the common close")
        clean = np.sum(np.diff(latent[:, ::stride], axis=1)**2, axis=1)
        noisy = np.sum(np.diff(observed[:, ::stride], axis=1)**2, axis=1)
        records.append({"stride": stride, "increments": n//stride,
                        "clean_mean": float(clean.mean()), "noisy_mean": float(noisy.mean()),
                        "noisy_mc_se": float(noisy.std(ddof=1)/np.sqrt(paths)),
                        "expected_noisy": sigma**2 + 2*(n//stride)*eta**2})
    return records


def stale_experiment(rng):
    common, independent = rng.normal(size=(2, 20000))
    a = common
    b = .8 * common + .6 * independent
    return {"synchronous": float(np.corrcoef(a, b)[0, 1]),
            "b_stale_one_step": float(np.corrcoef(a[1:], b[:-1])[0, 1]),
            "lag_restored_for_diagnosis": float(np.corrcoef(a[:-1], b[:-1])[0, 1]),
            "note": "lag alignment is retrospective diagnosis, not current observable information"}


def run():
    streams = [np.random.default_rng(s) for s in
               np.random.SeedSequence(CONFIG["seed"]).spawn(3)]
    x, truth = generate_daily(streams[0])
    predicted, protocol = forecasts(x, CONFIG["train"], CONFIG["window"], CONFIG["decay"])
    metrics, variance, oracle = evaluate(predicted, x, truth, CONFIG["train"])
    prices = 100 * np.exp(np.vstack([np.zeros(4), np.cumsum(x, axis=0)]))
    simple = np.expm1(x)
    weights = np.array(CONFIG["weights"])
    actual_portfolio_log = np.log1p(simple @ weights)
    weighted_log = x @ weights
    results = {"label": "SYNTHETIC", "assets": ASSETS, "config": CONFIG,
               "train_log_moments": describe(x[:CONFIG["train"]]),
               "full_sample_log_moments_descriptive_only": describe(x),
               "train_simple_covariance": covariance(simple[:CONFIG["train"]]).tolist(),
               "metrics_log_proxy": metrics,
               "max_daily_portfolio_log_gap": float(np.max(abs(actual_portfolio_log-weighted_log))),
               "sampling": sampling_experiment(streams[1]),
               "stale": stale_experiment(streams[2])}
    out = Path(__file__).resolve().parent / "runs" / datetime.now(timezone.utc).strftime(
        "run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    np.savez_compressed(out/"daily.npz", log_returns=x, prices=prices,
                        oracle_covariance=truth, predicted=predicted, protocol=protocol,
                        proxy_variance=variance, oracle_proxy_variance=oracle)
    (out/"results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2,
                                             allow_nan=False)+"\n", encoding="utf-8")
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"label": "SYNTHETIC", "python": platform.python_version(),
                "numpy": np.__version__, "code_sha256": digest(Path(__file__)),
                "files": {p.name: digest(p) for p in sorted(out.iterdir())},
                "protocol": "first 600 fit; 600 out-of-sample; hyperparameters fixed beforehand",
                "input_policy": "daily data saved; intraday/stale regenerated from child seeds and code",
                "limitations": ["zero conditional log mean is a DGP assumption",
                                "weighted logs are a linear risk proxy, not exact portfolio log return",
                                "no real feeds, fees, missing-data recovery or measured latency"]}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(out)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
