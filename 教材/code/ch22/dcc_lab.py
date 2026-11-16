"""Fit two-stage DCC-GARCH and compare one-step covariance forecasts."""
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from correlation_lab import correlation, covariance, dcc_step, samples, shrink

TRAIN = 120


def variance_path(u, p, initial):
    omega, a, b = p
    h = initial
    forecasts = []
    for value in u:
        forecasts.append(h)
        h = omega + a * value**2 + b * h
    return np.array(forecasts), h


def optimize(objective, starts, bounds, persistence_limit=0.999):
    constraint = {"type": "ineq", "fun": lambda p: persistence_limit - sum(p[-2:])}
    fits = [minimize(objective, x, method="SLSQP", bounds=bounds,
                     constraints=[constraint], options={"ftol": 1e-9, "maxiter": 300})
            for x in starts]
    valid = [f for f in fits if f.success and np.isfinite(f.fun)
             and constraint["fun"](f.x) >= -1e-8]
    if not valid:
        raise RuntimeError("no feasible converged fit")
    return min(valid, key=lambda f: f.fun).x


def gaussian_score(u, h):
    l = np.linalg.cholesky(h)
    z = np.linalg.solve(l, u)
    return float(2 * np.log(np.diag(l)).sum() + z @ z)


def correlation_path(z, target, params):
    q = target.copy()
    total = 0.0
    for row in z:
        total += gaussian_score(row, correlation(q))
        q, _ = dcc_step(q, row, target, *params)
    return total / len(z), q


def fit(training):
    # Unit conversion improves optimization conditioning and is common to all methods.
    mu = training.mean(axis=0)
    u = training - mu
    initial = u.var(axis=0)
    parameters, z_columns, next_variances = [], [], []
    for residual, v0 in zip(u.T, initial):
        def objective(p):
            h, _ = variance_path(residual, p, v0)
            return np.mean(np.log(h) + residual**2/h)
        p = optimize(objective, [(0.1*v0, .05, .85), (.5*v0, .1, .4)],
                     [(1e-7, 10*v0), (0, .999), (0, .999)])
        h, h_next = variance_path(residual, p, v0)
        parameters.append(p)
        z_columns.append(residual / np.sqrt(h))
        next_variances.append(h_next)
    z = np.column_stack(z_columns)
    target = z.T @ z / len(z)
    # Tiny fixed ridge guards the target against singularity.
    target = .9999*target + .0001*np.eye(target.shape[0])
    ab = optimize(lambda p: correlation_path(z, target, p)[0],
                  [(0.03, .90), (.15, .40), (0, 0)], [(0, .999), (0, .999)])
    _, q = correlation_path(z, target, ab)
    fixed = shrink(covariance(u))
    return {"mean": mu, "garch": np.array(parameters), "target": target,
            "dcc": ab, "h": np.array(next_variances), "q": q, "fixed": fixed}


def replay(model, returns):
    h = model["h"].copy()
    q = model["q"].copy()
    fixed = model["fixed"]
    ewm = fixed.copy()
    omega, a, b = model["garch"].T
    rows = []
    for t, value in enumerate(returns, TRAIN):
        d = np.sqrt(h)
        r = correlation(q)
        forecasts = {"dcc": r * np.outer(d, d),
                     "ccc": correlation(model["target"]) * np.outer(d, d),
                     "ewma": ewm, "static": fixed}
        scores = None
        if np.isfinite(value).all():
            u = value - model["mean"]
            scores = {name: gaussian_score(u, matrix) for name, matrix in forecasts.items()}
            q, _ = dcc_step(q, u / d, model["target"], *model["dcc"])
            h = omega + a*u**2 + b*h
            ewm = .94*ewm + .06*np.outer(u,u)
        rows.append({"t": t, "scores": scores, "dcc_eq_bond": float(r[0, 1]),
                     "matrices": {name: matrix.tolist() for name, matrix in forecasts.items()}})
    return rows


def experiment():
    x = 100*samples()
    model = fit(x[:TRAIN])
    rows = replay(model, x[TRAIN:])
    windows = {}
    for name, selected in [("all", rows), ("pre_change", rows[:20]), ("post_change", rows[20:])]:
        values = [r["scores"] for r in selected if r["scores"] is not None]
        windows[name] = {"n": len(values), "mean_loss": {
            method: float(np.mean([r[method] for r in values])) for method in values[0]}}
    return {"data_kind": "SYNTHETIC", "training_end_exclusive": TRAIN,
            "fit": {k: v.tolist() for k,v in model.items()}, "windows": windows, "rows": rows}


if __name__ == "__main__":
    result = experiment()
    out = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("dcc_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    report = out / "dcc.json"
    report.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(report)
    print(json.dumps({k: result[k] for k in ("fit", "windows")}, indent=2))
