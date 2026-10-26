"""SYNTHETIC factor attribution; forecasts and contemporaneous explanations differ."""
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ASSETS = ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"]
MODELS = ["market_frozen", "two_frozen", "two_rolling"]
CONFIG = {"seed": 20261027, "days": 1200, "train": 600,
          "change": 900, "window": 240, "hac_lags": 5,
          "factor_names": ["MKT_DEMO", "GROWTH_DEMO"], "rf": .00005}


def panel(value):
    value = np.asarray(value, dtype=float)
    if value.ndim != 2 or not np.isfinite(value).all():
        raise ValueError("finite two-dimensional panel required; no silent deletion")
    return value


def design(factors):
    factors = panel(factors)
    return np.column_stack([np.ones(len(factors)), factors])


def fit(factors, returns):
    x, y = design(factors), panel(returns)
    if len(x) != len(y) or len(x) <= x.shape[1]:
        raise ValueError("aligned observations and positive residual degrees required")
    beta, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise ValueError("unidentified coefficients: rank deficient design")
    return beta, y-x @ beta, float(singular[0]/singular[-1])


def hac_cov(factors, residual, lags=5):
    x = design(factors)
    u = np.asarray(residual, dtype=float)
    n, k = x.shape
    if (u.shape != (n,) or not np.isfinite(u).all() or n <= k
            or not isinstance(lags, int) or isinstance(lags, bool)
            or not 0 <= lags < n or np.linalg.matrix_rank(x) != k):
        raise ValueError("invalid residual, lag or design")
    scores = x*u[:, None]
    meat = scores.T @ scores
    for lag in range(1, lags+1):
        cross = scores[lag:].T @ scores[:-lag]
        meat += (1-lag/(lags+1))*(cross+cross.T)
    bread = np.linalg.solve(x.T @ x, np.eye(k))
    return (n/(n-k))*bread @ meat @ bread


def generate():
    rng = np.random.default_rng(CONFIG["seed"])
    n = CONFIG["days"]
    shock = rng.normal(size=(n, 2))
    market = .0003 + .01*shock[:, 0]
    growth = .0012 + .3*(market-.0003) + .006*shock[:, 1]
    factors = np.column_stack([market, growth])
    load = np.broadcast_to(np.array([[1.1, .8], [-.2, .4],
                                    [.1, -.4], [-.1, .2]]), (n, 4, 2)).copy()
    load[CONFIG["change"]:, 0] = [1.8, -.2]
    load[CONFIG["change"]:, 1] = [.4, .8]
    noise = rng.normal(size=(n, 4))*[.004, .002, .006, .003]
    excess = np.einsum("tik,tk->ti", load, factors)+noise
    return factors, excess, load


def prefit(factors, returns, start=600, window=240, available=None):
    f, y = panel(factors), panel(returns)
    n = len(f)
    if len(y) != n or f.shape[1] != 2 or not 3 < window <= start < n:
        raise ValueError("invalid dimensions or split")
    available = np.arange(n)+.1 if available is None else np.asarray(available)
    if available.shape != (n,) or not np.isfinite(available).all():
        raise ValueError("invalid availability")
    one = fit(f[:start, :1], y[:start])[0]
    one = np.vstack([one, np.zeros(y.shape[1])])
    two = fit(f[:start], y[:start])[0]
    estimates, forecasts, protocol = [], [], []
    for t in range(start, n):
        decision = t-.2
        if max(available[:t]) > decision:
            raise ValueError("training information not available at decision")
        rolling = fit(f[t-window:t], y[t-window:t])[0]
        b = np.stack([one, two, rolling])
        means = np.stack([f[:start].mean(axis=0), f[:start].mean(axis=0),
                          f[t-window:t].mean(axis=0)])
        forecasts.append(b[:, 0, :] + np.einsum("mk,mki->mi", means, b[:, 1:, :]))
        estimates.append(b)
        protocol.append([t, t-1, max(available[:t]), decision])
    return np.array(estimates), np.array(forecasts), np.array(protocol)


def attribute(beta, factor, observed, available_at, as_of):
    if not np.isfinite([available_at, as_of]).all() or available_at > as_of:
        raise ValueError("current factor/return unavailable; explanation cannot be published")
    beta, factor = panel(beta), np.asarray(factor, dtype=float)
    observed = np.asarray(observed, dtype=float)
    if (factor.shape != (beta.shape[0]-1,) or observed.shape != (beta.shape[1],)
            or not np.isfinite(factor).all() or not np.isfinite(observed).all()):
        raise ValueError("invalid attribution inputs")
    components = np.vstack([beta[0], factor[:, None]*beta[1:]])
    residual = observed-components.sum(axis=0)
    return components, residual


def sdf_example():
    probability = np.array([.5, .5])
    sdf = np.array([1.1, .8])
    payoffs = np.array([[1., 80., 120.], [1., 120., 80.]])
    state_prices = probability*sdf
    prices = state_prices @ payoffs
    gross = payoffs/prices
    rf_gross = 1/state_prices.sum()
    return {"states": ["bad", "good"], "probabilities": probability.tolist(),
            "sdf": sdf.tolist(), "state_prices": state_prices.tolist(),
            "payoffs": payoffs.tolist(), "prices": prices.tolist(),
            "risk_neutral_probabilities": (state_prices/state_prices.sum()).tolist(),
            "gross_rf": float(rf_gross),
            "expected_excess": (probability @ gross-rf_gross).tolist(),
            "euler_errors": (state_prices @ gross-1).tolist()}


def run():
    f, y, true_beta = generate()
    start = CONFIG["train"]
    b, forecast, protocol = prefit(f, y, start, CONFIG["window"])
    parts, residuals = [], []
    for j, t in enumerate(range(start, len(f))):
        row = [attribute(b[j, m], f[t], y[t], t+.1, t+.2) for m in range(3)]
        parts.append([r[0] for r in row])
        residuals.append([r[1] for r in row])
    parts, residuals = np.array(parts), np.array(residuals)
    alpha = {}
    for label, cols in [("market", 1), ("two", 2)]:
        coef, residual, condition = fit(f[:start, :cols], y[:start])
        se = np.array([np.sqrt(hac_cov(f[:start, :cols], residual[:, i],
                                     CONFIG["hac_lags"])[0, 0]) for i in range(4)])
        alpha[label] = {"intercept": coef[0].tolist(), "hac_se": se.tolist(),
                        "t_ratio": (coef[0]/se).tolist(), "condition": condition}
    metrics = {}
    times = np.arange(start, len(f))
    for label, mask in [("all", times >= start), ("before", times < CONFIG["change"]),
                        ("after", times >= CONFIG["change"])]:
        metrics[label] = {model: {
            "attribution_rmse": np.sqrt(np.mean(residuals[mask, m]**2, axis=0)).tolist(),
            "forecast_rmse": np.sqrt(np.mean((y[start:][mask]-forecast[mask, m])**2,
                                             axis=0)).tolist()}
            for m, model in enumerate(MODELS)}
    results = {"label": "SYNTHETIC", "config": CONFIG, "assets": ASSETS,
               "models": MODELS, "train_alpha": alpha, "metrics": metrics,
               "sdf": sdf_example(),
               "max_accounting_error": float(np.max(abs(parts.sum(axis=2)+residuals-y[start:, None, :])))}
    out = Path(__file__).resolve().parent/"runs"/datetime.now(timezone.utc).strftime(
        "run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    np.savez_compressed(out/"inputs_outputs.npz", factors=f, excess_returns=y,
                        true_beta=true_beta, estimated_beta=b, forecast=forecast,
                        components=parts, residuals=residuals, protocol=protocol)
    (out/"results.json").write_text(json.dumps(results, ensure_ascii=False,
                                             indent=2, allow_nan=False)+"\n", encoding="utf-8")
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"label": "SYNTHETIC", "python": platform.python_version(),
                "numpy": np.__version__, "code_sha256": digest(Path(__file__)),
                "files": {p.name: digest(p) for p in sorted(out.iterdir())},
                "policy": "fixed 600/600 split; window240 and HAC5 fixed before evaluation",
                "timing": "coefficients and forecasts t-.2; data t+.1; attribution t+.2",
                "limitations": ["factor DGP is not a proved equilibrium or real market",
                                "post-period factor explanations are not forecasts",
                                "no production data service or measured latency"]}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(out)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
