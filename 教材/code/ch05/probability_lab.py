"""第5章概率实验：人工状态、Bayes更新、混合分布与尾部模拟。"""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np


def probability_vector(value):
    p = np.array(value, dtype=float, copy=True)
    if (p.ndim != 1 or len(p) == 0 or not np.isfinite(p).all()
            or np.any(p < 0) or abs(float(p.sum()) - 1) > 1e-12):
        raise ValueError("finite nonnegative probabilities summing to one required")
    return p


def posterior_from_loglikelihood(prior, log_likelihood):
    p = probability_vector(prior)
    ell = np.asarray(log_likelihood, dtype=float)
    if ell.ndim != 2 or ell.shape[1] != len(p) or len(ell) == 0:
        raise ValueError("rows are observations, columns are states")
    if np.isnan(ell).any() or np.isposinf(ell).any():
        raise ValueError("log likelihood may be finite or negative infinity")
    log_prior = np.full(len(p), -np.inf)
    np.log(p, out=log_prior, where=p > 0)
    joint = ell + log_prior
    shift = joint.max(axis=1, keepdims=True)
    if not np.isfinite(shift).all():
        raise ValueError("some observations have zero modeled evidence")
    mass = np.exp(joint - shift)
    return mass / mass.sum(axis=1, keepdims=True)


def gaussian_logpdf(observations, mean, covariance):
    x = np.array(observations, dtype=float, copy=True, order="C")
    mu = np.asarray(mean, dtype=float)
    s = np.asarray(covariance, dtype=float)
    if x.ndim != 2 or len(x) == 0 or mu.shape != (x.shape[1],):
        raise ValueError("observation and mean axes mismatch")
    if s.shape != (len(mu), len(mu)) or not all(np.isfinite(a).all() for a in [x, mu, s]):
        raise ValueError("finite matching covariance required")
    scale = max(float(np.linalg.norm(s, 2)), np.finfo(float).tiny)
    if np.max(np.abs(s - s.T)) > 1e-12 * scale:
        raise ValueError("covariance must be symmetric")
    s = (s + s.T) / 2
    lower = np.linalg.cholesky(s)
    whitened = np.linalg.solve(lower, (x - mu).T)
    squared = np.sum(whitened ** 2, axis=0)
    log_determinant = 2 * np.log(np.diag(lower)).sum()
    return -.5 * (len(mu) * np.log(2 * np.pi) + log_determinant + squared)


def synthetic_model():
    prior = np.array([.95, .05])
    means = np.array([[.0002, .0001, .0001, 0], [-.015, .003, .004, .002]])
    correlation = np.array([[1, -.20, .20, .10], [-.20, 1, -.10, .05],
                            [.20, -.10, 1, .15], [.10, .05, .15, 1]])
    vols = np.array([[.008, .003, .006, .004], [.025, .010, .018, .012]])
    covariances = np.array([correlation * np.outer(v, v) for v in vols])
    return prior, means, covariances


def simulate_mixture(rng, count, prior, means, covariances):
    p = probability_vector(prior)
    if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or count <= 0:
        raise ValueError("positive integer sample count required")
    means, covariances = np.asarray(means), np.asarray(covariances)
    if means.ndim != 2 or means.shape[0] != len(p):
        raise ValueError("state and asset axes mismatch")
    d = means.shape[1]
    if covariances.shape != (len(p), d, d):
        raise ValueError("covariance axes mismatch")
    # 在抽样前验证所有状态，不能因某状态此次没抽中就跳过验证。
    factors = []
    for k in range(len(p)):
        gaussian_logpdf(np.zeros((1, d)), means[k], covariances[k])
        factors.append(np.linalg.cholesky((covariances[k] + covariances[k].T) / 2))
    states = rng.choice(len(p), size=count, p=p)
    returns = np.empty((count, d))
    for k in range(len(p)):
        selected = np.flatnonzero(states == k)
        z = rng.standard_normal((len(selected), d))
        returns[selected] = means[k] + z @ factors[k].T
    return states, returns


def mixture_moments(prior, means, covariances):
    p = probability_vector(prior)
    means, covariances = np.asarray(means, dtype=float), np.asarray(covariances, dtype=float)
    if (means.ndim != 2 or means.shape[0] != len(p)
            or covariances.shape != (len(p), means.shape[1], means.shape[1])):
        raise ValueError("mixture moment axes mismatch")
    if not np.isfinite(means).all() or not np.isfinite(covariances).all():
        raise ValueError("finite mixture parameters required")
    mean = p @ means
    centered = means - mean
    covariance = np.einsum("k,kij->ij", p, covariances)
    covariance += np.einsum("k,ki,kj->ij", p, centered, centered)
    return mean, covariance


def exact_loss_tail(prior, means, covariances, weights, loss_threshold):
    p = probability_vector(prior)
    w = np.asarray(weights, dtype=float)
    if (w.ndim != 1 or not np.isfinite(w).all() or not np.isfinite(loss_threshold)
            or np.asarray(means).shape != (len(p), len(w))
            or np.asarray(covariances).shape != (len(p), len(w), len(w))):
        raise ValueError("finite matching tail inputs required")
    total = 0.
    for k in range(len(p)):
        gaussian_logpdf(np.zeros((1, len(w))), means[k], covariances[k])
        mu = float(w @ means[k])
        variance = float(w @ covariances[k] @ w)
        if variance <= 0:
            raise ValueError("positive portfolio variance required")
        total += p[k] * .5 * math.erfc((mu + loss_threshold) / np.sqrt(2 * variance))
    return float(total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.count < 1000 or args.seed < 0:
        raise ValueError("count >= 1000 and seed >= 0 required")
    seed_sequence = np.random.SeedSequence(args.seed)
    children = seed_sequence.spawn(3)
    streams = [np.random.Generator(np.random.PCG64(child)) for child in children]
    prior, means, covariances = synthetic_model()
    states, returns = simulate_mixture(streams[0], args.count, prior, means, covariances)
    log_likelihood = np.column_stack([gaussian_logpdf(returns, means[k], covariances[k])
                                     for k in range(len(prior))])
    posterior = posterior_from_loglikelihood(prior, log_likelihood)
    mean, covariance = mixture_moments(prior, means, covariances)
    weights, threshold = np.array([.4, .25, .2, .15]), .02
    losses = -(returns @ weights)
    hits = int(np.count_nonzero(losses > threshold))
    estimate = hits / args.count
    standard_error = math.sqrt(estimate * (1 - estimate) / args.count)
    exact = exact_loss_tail(prior, means, covariances, weights, threshold)
    normal = streams[1].standard_normal(args.count)
    standardized_t = streams[2].standard_t(5, args.count) * np.sqrt(3 / 5)
    one_alert = posterior_from_loglikelihood([.99, .01], np.log([[.05, .90]]))[0, 1]
    wrong_duplicate = posterior_from_loglikelihood([.99, .01], 2 * np.log([[.05, .90]]))[0, 1]
    output = args.out or Path(__file__).parent / "runs" / datetime.now(
        timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    preview = np.column_stack([states[:32], returns[:32], posterior[:32, 1]])
    np.savetxt(output / "synthetic_preview.csv", preview, delimiter=",",
               header="state,EQ_DEMO,BOND_DEMO,GOLD_DEMO,FX_DEMO,posterior_stress", comments="")
    np.savez(output / "model.npz", prior=prior, means=means, covariances=covariances, weights=weights)
    report = {"data_kind": "synthetic", "numpy": np.__version__, "seed": args.seed,
              "bit_generator": "PCG64", "spawn_keys": [list(c.spawn_key) for c in children],
              "draws": args.count, "asset_order": ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"],
              "state_order": ["NORMAL_DEMO", "STRESS_DEMO"],
              "sampling": "independent mixture draws, not a historical or Markov time series",
              "one_alert_posterior": float(one_alert),
              "incorrect_duplicate_posterior": float(wrong_duplicate),
              "correct_exact_duplicate_posterior": float(one_alert),
              "theoretical_mean": mean.tolist(), "theoretical_covariance": covariance.tolist(),
              "simulated_mean": returns.mean(axis=0).tolist(),
              "average_posterior_stress": float(posterior[:, 1].mean()),
              "loss_threshold": threshold, "tail_hits": hits, "tail_estimate": estimate,
              "tail_exact_under_model": exact, "tail_mc_standard_error": standard_error,
              "tail_error_in_estimated_se": (estimate - exact) / standard_error if standard_error else None,
              "normal_right_tail_3_exact": .5 * math.erfc(3 / math.sqrt(2)),
              "normal_right_tail_3_mc": float(np.mean(normal > 3)),
              "unit_variance_t5_right_tail_3_mc": float(np.mean(standardized_t > 3)),
              "interpretation": "model arithmetic and Monte Carlo error only; no empirical market calibration"}
    (output / "manifest.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    print(f"Artifacts: {output.resolve()}")


if __name__ == "__main__":
    main()
