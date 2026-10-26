"""SYNTHETIC dependence diagnostics and auditable fire-sale stress scenarios."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np

ASSETS = ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"]
SEED = 20261027


def tail_rate(x, y, probability):
    cutoff = NormalDist().inv_cdf(probability)
    mask = x <= cutoff
    count = int(mask.sum())
    joint = int(np.sum(mask & (y <= cutoff)))
    return {"u": probability, "conditioning_count": count, "joint_count": joint,
            "conditional_rate": joint / count if count else None}


def dependence(n=80000):
    rng = np.random.default_rng(SEED)
    factor = rng.normal(size=n)
    noise = rng.normal(size=(n, 4))
    noise[:, 0] = 0
    beta = np.array([1.0, .6, -.2, .3])
    calm = .01 * (factor[:, None] * beta + noise)
    volatile = .01 * (3 * factor[:, None] * beta + noise)
    c0, c1 = np.corrcoef(calm.T), np.corrcoef(volatile.T)
    delta = np.var(volatile[:, 0]) / np.var(calm[:, 0]) - 1
    adjusted = c1[0, 1] / np.sqrt(1 + delta * (1 - c1[0, 1] ** 2))
    z = rng.normal(size=(n, 2))
    rho = .4
    gaussian = np.column_stack((z[:, 0], rho * z[:, 0] + np.sqrt(1-rho**2) * z[:, 1]))
    shared = rng.random(n) < rho
    mixture = np.column_stack((z[:, 0], np.where(shared, z[:, 0], z[:, 1])))
    stats = {"calm_correlation": float(c0[0, 1]),
             "volatile_correlation": float(c1[0, 1]),
             "variance_adjusted_correlation": float(adjusted),
             "delta": float(delta)}
    for name, sample in (("gaussian", gaussian), ("mixture", mixture)):
        stats[name] = {"correlation": float(np.corrcoef(sample.T)[0, 1]),
                       "tails": [tail_rate(sample[:, 0], sample[:, 1], u)
                                 for u in (.05, .01)]}
    arrays = {"factor": factor, "noise": noise, "calm": calm, "volatile": volatile,
              "gaussian": gaussian, "mixture": mixture, "mixture_shared": shared}
    return stats, arrays


def configuration():
    return {"assets": ASSETS, "institutions": ["A", "B", "C"],
            "holdings_units": [[50, 30, 10, 10], [10, 60, 20, 10], [0, 20, 50, 30]],
            "initial_prices": [1, 1, 1, 1], "debt": [80, 80, 80],
            "leverage_cap": 5.0, "external_drop": [.08, 0, 0, 0],
            "depth_units": [100, 100, 100, 100],
            "available_at": "2026-10-26T00:00:00+00:00",
            "decision_at": "2026-10-27T00:00:00+00:00",
            "time_kind": "SYNTHETIC protocol; rounds are not measured seconds"}


def validate(cfg):
    q = np.asarray(cfg["holdings_units"], float)
    p = np.asarray(cfg["initial_prices"], float)
    d = np.asarray(cfg["debt"], float)
    shock = np.asarray(cfg["external_drop"], float)
    depth = np.asarray(cfg["depth_units"], float)
    if (q.ndim != 2 or p.shape != (q.shape[1],) or
            d.shape != (q.shape[0],) or shock.shape != p.shape or depth.shape != p.shape):
        raise ValueError("SHAPE")
    if not all(np.isfinite(a).all() for a in (q, p, d, shock, depth)):
        raise ValueError("NONFINITE")
    cap = float(cfg["leverage_cap"])
    if (np.any(q < 0) or np.any(p <= 0) or np.any(d < 0) or np.any(depth <= 0)
            or np.any(shock < 0) or np.any(shock >= 1) or not np.isfinite(cap) or cap <= 1):
        raise ValueError("DOMAIN")
    available = datetime.fromisoformat(cfg["available_at"])
    decision = datetime.fromisoformat(cfg["decision_at"])
    if available.tzinfo is None or decision.tzinfo is None or available > decision:
        raise ValueError("PIT_TIME")
    if np.any(q @ p - d <= 0):
        raise ValueError("NONPOSITIVE_INITIAL_EQUITY")
    return q.copy(), p.copy(), d.copy(), shock, depth, cap


def stress(cfg, impact, tolerance=1e-9, max_rounds=300):
    q, initial_p, debt, shock, depth, cap = validate(cfg)
    if (not np.isfinite(impact) or impact < 0 or not np.isfinite(tolerance)
            or tolerance <= 0 or max_rounds < 1):
        raise ValueError("ALGORITHM_CONFIG")
    initial_equity = q @ initial_p - debt
    external_p = initial_p * (1 - shock)
    p = external_p.copy()
    direct_loss = q @ (initial_p - external_p)
    cumulative = np.zeros_like(p)
    records = []
    status = "MAX_ROUNDS"
    for k in range(max_rounds):
        assets = q @ p
        equity = assets - debt
        if np.any(equity <= 0):
            status = "INSOLVENT_STOP"
            break
        need = np.maximum(assets - cap * equity, 0)
        if np.max(need) <= tolerance:
            status = "CONVERGED"
            break
        sale_value = np.minimum(np.minimum(need, debt), assets)
        fraction = np.divide(sale_value, assets, out=np.zeros_like(assets), where=assets > 0)
        sold = q * fraction[:, None]  # Synchronous orders from the same pre-round state.
        cumulative += sold.sum(axis=0)
        new_p = external_p * np.exp(-impact * cumulative / depth)
        if not np.isfinite(new_p).all() or np.any(new_p <= 0):
            raise ArithmeticError("PRICE_NUMERICAL_RANGE")
        proceeds = sold @ new_p  # Single clearing price; outside buyers absorb sales.
        next_q = q - sold
        next_debt = debt - proceeds
        next_equity = next_q @ new_p - next_debt
        mark_loss = q @ (p - new_p)
        accounting_error = next_equity - (equity - mark_loss)
        if np.max(np.abs(accounting_error)) > 1e-9 or np.min(next_debt) < -1e-9:
            raise ArithmeticError("ACCOUNTING")
        records.append({"round": k + 1, "price_before": p.tolist(),
                        "price_after": new_p.tolist(), "sold_units": sold.tolist(),
                        "proceeds": proceeds.tolist(), "debt_after": next_debt.tolist(),
                        "equity_after": next_equity.tolist(), "mark_loss": mark_loss.tolist(),
                        "accounting_error_max": float(np.max(np.abs(accounting_error)))})
        q, debt, p = next_q, next_debt, new_p
    equity = q @ p - debt
    # A limit reached on the last iteration is reported explicitly.
    if np.any(equity <= 0):
        status = "INSOLVENT_STOP"
    elif np.max(np.maximum(q @ p - cap * equity, 0)) <= tolerance:
        status = "CONVERGED"
    loss = initial_equity - equity
    return {"impact": impact, "status": status, "rounds": len(records),
            "direct_loss": direct_loss.tolist(), "total_loss": loss.tolist(),
            "endogenous_loss": (loss-direct_loss).tolist(),
            "final_prices": p.tolist(), "final_holdings": q.tolist(),
            "final_debt": debt.tolist(), "final_equity": equity.tolist(),
            "leverage_excess_value": np.maximum(q @ p-cap*equity, 0).tolist(),
            "trace": records}


def linear_network(H, initial, tolerance=1e-12, max_steps=10000):
    H, initial = np.asarray(H, float), np.asarray(initial, float)
    if H.shape != (initial.size, initial.size) or np.any(H < 0) or np.any(initial < 0):
        raise ValueError("NETWORK_DOMAIN")
    if not np.isfinite(H).all() or not np.isfinite(initial).all():
        raise ValueError("NETWORK_NONFINITE")
    radius = float(np.max(np.abs(np.linalg.eigvals(H))))
    if radius >= 1:
        raise ValueError("UNSTABLE_LINEARIZATION")
    total = initial.copy()
    increment = initial.copy()
    for _ in range(max_steps):
        increment = H @ increment
        total += increment
        if np.max(np.abs(increment)) <= tolerance:
            exact = np.linalg.solve(np.eye(initial.size)-H, initial)
            return {"radius": radius, "total": total.tolist(),
                    "solve_error": float(np.max(np.abs(total-exact)))}
    raise RuntimeError("NETWORK_NOT_CONVERGED")


def main():
    stats, arrays = dependence()
    cfg = configuration()
    scenarios = [stress(cfg, a) for a in (0.0, .05, .15)]
    network = linear_network([[0, .2, 0], [.1, 0, .3], [0, .1, 0]], [1, 0, 0])
    result = {"data_kind": "SYNTHETIC", "dependence": stats, "network": network,
              "stress": [{k: v for k, v in s.items() if k != "trace"} for s in scenarios]}
    out = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(out / "samples.npz", **arrays)
    files = {"configuration.json": cfg, "results.json": result, "traces.json": scenarios}
    for name, data in files.items():
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    manifest = {"data_kind": "SYNTHETIC", "seed": SEED, "n": 80000,
                "python": platform.python_version(), "numpy": np.__version__,
                "impact_grid": [0, .05, .15], "tolerance": 1e-9, "max_rounds": 300,
                "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "files_sha256": hashes,
                "boundary": "Outside buyers and lenders; no defaults, cash buffer, derivatives or forecast."}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(out.resolve())


if __name__ == "__main__":
    main()
