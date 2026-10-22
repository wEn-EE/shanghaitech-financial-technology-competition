"""第4章数值优化实验；所有协方差与目标均为人工构造。"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np


def vector(value, name="vector"):
    x = np.array(value, dtype=float, copy=True)
    if x.ndim != 1 or x.size == 0 or not np.isfinite(x).all():
        raise ValueError(f"{name} must be a nonempty finite vector")
    return x


def spd(value):
    s = np.array(value, dtype=float, copy=True, order="C")
    if (s.ndim != 2 or s.shape[0] == 0 or s.shape[0] != s.shape[1]
            or not np.isfinite(s).all()):
        raise ValueError("a finite square matrix is required")
    scale = max(float(np.linalg.norm(s, 2)), np.finfo(float).tiny)
    if np.max(np.abs(s - s.T)) > 1e-12 * scale:
        raise ValueError("matrix must be symmetric")
    s = (s + s.T) / 2
    np.linalg.cholesky(s)  # 不静默修复奇异或不定矩阵。
    return s


def central_gradient(fun, point, relative_step=1e-5):
    x = vector(point)
    if not np.isfinite(relative_step) or relative_step <= 0:
        raise ValueError("positive finite difference step required")
    gradient = np.empty_like(x)
    for j in range(len(x)):
        step = relative_step * max(1.0, abs(x[j]))
        right, left = x.copy(), x.copy()
        right[j] += step
        left[j] -= step
        gradient[j] = (fun(right) - fun(left)) / (2 * step)
    if not np.isfinite(gradient).all():
        raise ValueError("difference crossed domain or produced non-finite values")
    return gradient


def minimize(fun, grad, initial, hess=None, positive=False, tol=1e-9, max_iter=5000):
    x = vector(initial)
    if not np.isfinite(tol) or tol <= 0 or max_iter < 0:
        raise ValueError("invalid tolerance or iteration limit")
    if positive and np.any(x <= 0):
        raise ValueError("strictly positive initial point required")
    history = []
    for iteration in range(max_iter + 1):
        value = float(fun(x))
        g = vector(grad(x), "gradient")
        if g.shape != x.shape or not np.isfinite(value):
            raise ValueError("invalid objective or gradient")
        norm = float(np.linalg.norm(g))
        history.append({"iteration": iteration, "objective": value, "gradient_norm": norm})
        if norm <= tol:
            return {"x": x, "converged": True, "reason": "gradient_tolerance", "history": history}
        if iteration == max_iter:
            break
        direction = -g if hess is None else np.linalg.solve(spd(hess(x)), -g)
        slope = float(g @ direction)
        if not np.isfinite(slope) or slope >= 0:
            raise ValueError("direction is not a finite descent direction")
        step = 1.0
        accepted = False
        for _ in range(60):
            candidate = x + step * direction
            if np.isfinite(candidate).all() and (not positive or np.all(candidate > 0)):
                new_value = float(fun(candidate))
                if np.isfinite(new_value) and new_value <= value + 1e-4 * step * slope:
                    accepted = True
                    break
            step *= 0.5
        if not accepted:
            return {"x": x, "converged": False, "reason": "line_search_failed", "history": history}
        history[-1]["step"] = step
        x = candidate
    return {"x": x, "converged": False, "reason": "iteration_limit", "history": history}


def project_simplex(value):
    v = vector(value)
    ordered = np.sort(v)[::-1]
    thresholds = (np.cumsum(ordered) - 1) / np.arange(1, len(v) + 1)
    active = np.flatnonzero(ordered > thresholds)
    theta = thresholds[active[-1]]
    return np.maximum(v - theta, 0.0)


def minimum_variance(covariance, tol=1e-9, max_iter=20000):
    s = spd(covariance)
    # 正的公共尺度不改变最优权重；使停止阈值对应无量纲问题。
    c = s / np.mean(np.diag(s))
    step = 1.0 / np.linalg.eigvalsh(c)[-1]
    w = np.full(len(c), 1 / len(c))
    history = []
    for iteration in range(max_iter + 1):
        candidate = project_simplex(w - step * (c @ w))
        mapping = float(np.linalg.norm((w - candidate) / step))
        history.append({"iteration": iteration, "objective": float(0.5 * w @ c @ w),
                        "mapping_norm": mapping})
        if mapping <= tol:
            return {"x": w, "converged": True, "reason": "projected_gradient_tolerance",
                    "history": history}
        if iteration == max_iter:
            break
        w = candidate
    return {"x": w, "converged": False, "reason": "iteration_limit", "history": history}


def risk_contributions(weights, covariance):
    w = vector(weights, "weights")
    s = spd(covariance)
    if len(w) != len(s):
        raise ValueError("weights and covariance axes differ")
    variance = float(w @ s @ w)
    if variance <= 0:
        raise ValueError("positive portfolio variance required")
    volatility = np.sqrt(variance)
    absolute = w * (s @ w) / volatility
    return absolute, absolute / volatility


def risk_budget(covariance, budget):
    s = spd(covariance)
    b = vector(budget, "budget")
    if len(b) != len(s) or np.any(b <= 0) or abs(float(b.sum()) - 1) > 1e-12:
        raise ValueError("strictly positive budgets summing to one required")
    c = s / np.mean(np.diag(s))
    fun = lambda x: float(0.5 * x @ c @ x - b @ np.log(x))
    grad = lambda x: c @ x - b / x
    hess = lambda x: c + np.diag(b / x ** 2)
    result = minimize(fun, grad, np.sqrt(b / np.diag(c)), hess=hess, positive=True)
    # 失败时不发布一个貌似有效的风险预算结果。
    if not result["converged"]:
        raise RuntimeError(result["reason"])
    result["weights"] = result["x"] / result["x"].sum()
    result["relative_contributions"] = risk_contributions(result["weights"], s)[1]
    return result


def synthetic_covariance():
    vol = np.array([0.020, 0.008, 0.015, 0.010])
    correlation = np.array([[1, -.15, .25, .10], [-.15, 1, -.10, .05],
                            [.25, -.10, 1, .20], [.10, .05, .20, 1]])
    return spd(correlation * np.outer(vol, vol))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or Path(__file__).parent / "runs" / datetime.now(
        timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    q = np.array([[4., 1.], [1., 3.]])
    linear = np.array([-1., -2.])
    fun = lambda x: float(0.5 * x @ q @ x + linear @ x)
    grad = lambda x: q @ x + linear
    initial = np.array([2., -1.])
    gradient_error = float(np.max(np.abs(central_gradient(fun, initial) - grad(initial))))
    gd = minimize(fun, grad, initial)
    newton = minimize(fun, grad, initial, hess=lambda x: q)
    covariance = synthetic_covariance()
    mv = minimum_variance(covariance)
    if not gd["converged"] or not newton["converged"] or not mv["converged"]:
        raise RuntimeError("a numerical solve did not converge")
    budget = np.array([.4, .2, .2, .2])
    rb = risk_budget(covariance, budget)
    np.savetxt(output / "synthetic_covariance.csv", covariance, delimiter=",")
    np.savez(output / "solutions.npz", gradient_solution=gd["x"], newton_solution=newton["x"],
             minimum_variance=mv["x"], risk_budget=rb["weights"], budget=budget)
    for name, result in {"gradient": gd, "newton": newton, "minimum_variance": mv,
                         "risk_budget": rb}.items():
        (output / f"{name}_history.json").write_text(
            json.dumps(result["history"], indent=2, allow_nan=False), encoding="utf-8")
    grid = np.linspace(0, 1, 101)
    integral = float(np.trapezoid(grid ** 2, grid))
    report = {"data_kind": "synthetic", "numpy": np.__version__,
              "asset_order": ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"],
              "covariance_frequency": "one artificial observation period",
              "gradient_max_abs_error": gradient_error,
              "quadratic_reference": np.linalg.solve(q, -linear).tolist(),
              "gd_solution": gd["x"].tolist(), "newton_solution": newton["x"].tolist(),
              "gd_updates": len(gd["history"]) - 1, "newton_updates": len(newton["history"]) - 1,
              "minimum_variance_weights": mv["x"].tolist(),
              "minimum_variance_mapping": mv["history"][-1]["mapping_norm"],
              "risk_budget_target": budget.tolist(), "risk_budget_weights": rb["weights"].tolist(),
              "risk_budget_relative_contributions": rb["relative_contributions"].tolist(),
              "risk_budget_max_abs_error": float(np.max(np.abs(rb["relative_contributions"] - budget))),
              "trapezoid_x_squared": integral, "integration_absolute_error": abs(integral - 1 / 3),
              "interpretation": "numerical checks only; no market state accuracy or strategy performance"}
    (output / "manifest.json").write_text(json.dumps(report, indent=2, allow_nan=False),
                                         encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    print(f"Artifacts: {output.resolve()}")


if __name__ == "__main__":
    main()

