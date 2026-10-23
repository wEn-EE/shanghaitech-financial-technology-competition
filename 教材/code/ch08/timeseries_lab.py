"""SYNTHETIC time-series lab; run with the existing Anaconda Python."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import platform
import warnings

import numpy as np
import pandas as pd
import scipy
from scipy.stats import norm
import statsmodels
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA

ASSETS = ("EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO")
SEED, TRAIN_END, VALID_END, N = 20261024, 600, 800, 1200
WINDOWS = (120, 240)


def vector(x, minimum=4):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < minimum or not np.isfinite(x).all():
        raise ValueError("Require a finite 1-D series of sufficient length")
    return x


def fit_ar1(x):
    x = vector(x)
    lag, target = x[:-1], x[1:]
    z, y = lag - lag.mean(), target - target.mean()
    denominator = float(z @ z)
    if denominator <= 0:
        raise ValueError("Constant lag: AR coefficient is unidentified")
    phi = float(z @ y / denominator)
    c = float(target.mean() - phi * lag.mean())
    residual = target - c - phi * lag
    variance = float(residual @ residual / len(residual))
    if abs(phi) >= 1 or variance <= 0:
        raise ValueError("Stationary AR(1) baseline invalid; do not clip silently")
    return {"c": c, "phi": phi, "variance": variance, "pairs": len(residual)}


def predict_ar1(model, last, horizon=1):
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    phi, c, variance = model["phi"], model["c"], model["variance"]
    if not np.isfinite([phi, c, variance, last]).all() or abs(phi) >= 1 or variance <= 0:
        raise ValueError("Invalid stationary AR(1) forecast inputs")
    mu = c / (1 - phi)
    mean = mu + phi ** horizon * (last - mu)
    # A finite sum also works accurately near a unit root.
    error_variance = variance * sum(phi ** (2 * j) for j in range(horizon))
    return float(mean), float(error_variance)


def simulate():
    rng = np.random.Generator(np.random.PCG64(SEED))
    burn = 500
    phi = np.array([.45, .20, -.15, .05])
    sigma = np.array([.01, .003, .008, .005])
    state = np.zeros(4)
    rows = []
    for t in range(-burn, N):
        p, s = phi.copy(), sigma.copy()
        if t >= 1000:
            p[0], s[0] = -.25, .02
        noise = np.sqrt(.35) * rng.normal() + np.sqrt(.65) * rng.normal(size=4)
        state = p * state + s * noise
        if t >= 0:
            rows.append(state.copy())
    frame = pd.DataFrame(rows, columns=ASSETS)
    frame.insert(0, "available_time", np.arange(N) + .1)
    frame.insert(0, "event_time", np.arange(N))
    frame.insert(0, "source", "SYNTHETIC")
    return frame


def forecast_record(x, available, t, model_name, window=None):
    """Read only x[:t]; target value is attached by the evaluator later."""
    if t < TRAIN_END or t > len(x) or len(x) != len(available):
        raise ValueError("Invalid forecast origin")
    decision = t - .2
    end = TRAIN_END if model_name in ("zero", "fixed_ar1") else t
    if model_name == "rolling_ar1":
        if window is None or window < 4 or window > t:
            raise ValueError("Invalid rolling window")
        start = t - window
    elif model_name in ("zero", "fixed_ar1"):
        start = 0
    else:
        raise ValueError("Unknown model")
    past = vector(x[start:end])
    times = vector(available[start:end])
    if np.any(np.diff(times) <= 0):
        raise ValueError("This lab requires ordered, non-revised availability")
    cutoff, ready = end - .5, end - .25
    if times.max() > cutoff or ready > decision or available[t - 1] > decision:
        raise ValueError("PIT violation: model or lag not available")
    if model_name == "zero":
        model = {"c": 0., "phi": 0., "variance": float(np.mean(past[1:] ** 2)),
                 "pairs": len(past) - 1}
        mean, variance = predict_ar1(model, 0.)
    else:
        model = fit_ar1(past)
        mean, variance = predict_ar1(model, float(x[t - 1]))
    width = float(norm.ppf(.975) * np.sqrt(variance))
    return {"t": t, "model": model_name, "window": window or 0,
            "train_start": start, "train_end_exclusive": end,
            "train_max_available": float(times.max()), "fit_cutoff": cutoff,
            "model_ready": ready, "decision_time": decision,
            "lag_available": float(available[t - 1]),
            "model_version": f"{model_name}:{start}:{end}",
            **model, "mean": mean, "forecast_variance": variance,
            "lower": mean - width, "upper": mean + width}


def evaluate(x, available, start, stop, model_name, window=None):
    rows = []
    for t in range(start, stop):
        row = forecast_record(x, available, t, model_name, window)
        row.update(actual=float(x[t]), target_available=float(available[t]))
        rows.append(row)
    return pd.DataFrame(rows)


def metrics(frame):
    e = frame["actual"] - frame["mean"]
    lo, hi, y = frame["lower"], frame["upper"], frame["actual"]
    score = hi - lo + 40 * (lo - y).clip(lower=0) + 40 * (y - hi).clip(lower=0)
    return {"n": len(frame), "rmse": float(np.sqrt(np.mean(e ** 2))),
            "coverage95": float(((y >= lo) & (y <= hi)).mean()),
            "mean_width": float((hi - lo).mean()), "interval_score95": float(score.mean())}


def diagnostics(x):
    x = vector(x, 40)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        a = adfuller(x, maxlag=8, regression="c", autolag="AIC")
        k = kpss(x, regression="c", nlags=8)
        fit = fit_ar1(x)
        e = x[1:] - fit["c"] - fit["phi"] * x[:-1]
        lb = acorr_ljungbox(e, lags=[10], model_df=1, return_df=True)
        lb2 = acorr_ljungbox(e ** 2, lags=[10], model_df=0, return_df=True)
    return {"adf_stat": float(a[0]), "adf_p": float(a[1]), "adf_lags": int(a[2]),
            "kpss_stat": float(k[0]), "kpss_table_p": float(k[1]), "kpss_lags": int(k[2]),
            "lb_residual_p": float(lb.lb_pvalue.iloc[0]),
            "lb_squared_residual_p": float(lb2.lb_pvalue.iloc[0]),
            "acf": acf(x, nlags=12, fft=False).tolist(),
            "pacf": pacf(x, nlags=12, method="ywm").tolist(),
            "warnings": [str(w.message) for w in caught]}


def main():
    frame = simulate()
    available = frame.available_time.to_numpy()
    all_predictions, selection, summary, diag = [], {}, {}, {}
    for asset in ASSETS:
        x = frame[asset].to_numpy()
        scores = {w: metrics(evaluate(x, available, TRAIN_END, VALID_END,
                                      "rolling_ar1", w))["rmse"] for w in WINDOWS}
        chosen = min(WINDOWS, key=lambda w: (scores[w], w))
        selection[asset] = {"validation_rmse": scores, "chosen_window": chosen,
                            "selection_ready": VALID_END - .25}
        diag[asset] = diagnostics(x[:TRAIN_END])
        summary[asset] = {}
        for name in ("zero", "fixed_ar1", "rolling_ar1"):
            pred = evaluate(x, available, VALID_END, N, name,
                            chosen if name == "rolling_ar1" else None)
            pred.insert(0, "asset", asset)
            pred["selection_ready"] = VALID_END - .25
            if not (pred.selection_ready <= pred.decision_time).all():
                raise ValueError("Selection not ready before decision")
            summary[asset][name] = {"all_test": metrics(pred),
                                   "first_200": metrics(pred[pred.t < 1000]),
                                   "last_200": metrics(pred[pred.t >= 1000])}
            all_predictions.append(pred)
    # Independent package demonstration, in percentage points for numerical scaling.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        arima = ARIMA(100 * frame.EQ_DEMO.iloc[:TRAIN_END].to_numpy(),
                      order=(1, 0, 0), trend="c", missing="raise").fit()
    package_fit = {"parameter_names": arima.param_names, "parameters": arima.params.tolist(),
                   "converged": bool(arima.mle_retvals.get("converged", False)),
                   "warnings": [str(w.message) for w in caught]}
    out = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    frame.to_csv(out / "synthetic.csv", index=False, float_format="%.17g")
    pd.concat(all_predictions).to_csv(out / "predictions.csv", index=False, float_format="%.17g")
    manifest = {"source": "SYNTHETIC", "seed": SEED, "rng": "PCG64", "burn_in": 500,
                "split": [TRAIN_END, VALID_END, N], "candidate_windows": WINDOWS,
                "known_simulator_break": 1000, "common_noise_variance_share": .35,
                "selection": selection, "diagnostics_training_only": diag,
                "test_metrics": summary, "package_arima_training_only": package_fit,
                "versions": {"python": platform.python_version(), "numpy": np.__version__,
                             "pandas": pd.__version__, "scipy": scipy.__version__,
                             "statsmodels": statsmodels.__version__},
                "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [Path(__file__), out / "synthetic.csv", out / "predictions.csv"]}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                                                 allow_nan=False), encoding="utf-8")
    print(out.resolve())
    print(json.dumps({"selection": selection, "EQ_DEMO": summary["EQ_DEMO"],
                      "package_fit": package_fit}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
