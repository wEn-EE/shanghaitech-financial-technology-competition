"""Chapter 6: SYNTHETIC inference lab; existing NumPy/SciPy only."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import scipy
from scipy import stats

ASSETS = ("EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO")


def integer(value, low, high=None):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError("integer required")
    if value < low or (high is not None and value > high):
        raise ValueError("integer outside allowed range")
    return int(value)


def level(alpha):
    if not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    return float(alpha)


def sample(values):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("need at least two finite observations; no silent deletion")
    return x


def mean_t(values, mu0=0.0, alpha=0.05):
    x = sample(values)
    level(alpha)
    if not np.isfinite(mu0):
        raise ValueError("mu0 must be finite")
    n = len(x)
    mean = float(x.mean())
    se = float(x.std(ddof=1) / np.sqrt(n))
    if not np.isfinite(se) or se <= 0:
        raise ValueError("nonpositive or nonfinite standard error")
    statistic = (mean - mu0) / se
    radius = stats.t.ppf(1 - alpha / 2, n - 1) * se
    return {"mean": mean, "se": se, "t": float(statistic),
            "p_two_sided": float(2 * stats.t.sf(abs(statistic), n - 1)),
            "ci": [float(mean - radius), float(mean + radius)]}


def proportion_ci(k, n, alpha=0.05, method="wilson"):
    n = integer(n, 1)
    k = integer(k, 0, n)
    level(alpha)
    p = k / n
    z = stats.norm.ppf(1 - alpha / 2)
    if method == "wald":
        radius = z * np.sqrt(p * (1 - p) / n)
        return float(p - radius), float(p + radius)
    if method == "wilson":
        den = 1 + z * z / n
        center = (p + z * z / (2 * n)) / den
        radius = z / den * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        lo = 0.0 if k == 0 else max(0.0, float(center - radius))
        hi = 1.0 if k == n else min(1.0, float(center + radius))
        return lo, hi
    if method == "exact":
        lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
        hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
        return float(lo), float(hi)
    raise ValueError("method must be wald, wilson or exact")


def adjust_p(values, method="bh"):
    p = np.asarray(values, dtype=float)
    if p.ndim != 1 or p.size == 0 or not np.isfinite(p).all():
        raise ValueError("need a nonempty finite p-value vector")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("p-values outside [0, 1]")
    m = len(p)
    if method == "bonferroni":
        return np.minimum(1.0, m * p)
    if method not in ("bh", "by"):
        raise ValueError("unknown adjustment")
    order = np.argsort(p, kind="stable")
    multiplier = 1.0 if method == "bh" else np.sum(1.0 / np.arange(1, m + 1))
    scaled = p[order] * m * multiplier / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(scaled[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(1.0, adjusted)
    return out


def hac_se(values, lag):
    x = sample(values)
    n = len(x)
    lag = integer(lag, 0, n - 1)
    residual = x - x.mean()
    omega = float(residual @ residual / n)
    for h in range(1, lag + 1):
        gamma = float(residual[h:] @ residual[:-h] / n)
        omega += 2 * (1 - h / (lag + 1)) * gamma
    if not np.isfinite(omega) or omega <= 0:
        raise ValueError("nonpositive long-run variance; inspect data/configuration")
    return float(np.sqrt(omega / n))


def circular_bootstrap_ci(values, rng, block=12, draws=399, alpha=0.05):
    x = sample(values)
    n = len(x)
    block = integer(block, 1, n)
    draws = integer(draws, 2)
    level(alpha)
    count = (n + block - 1) // block
    starts = rng.integers(0, n, size=(draws, count))
    indices = (starts[..., None] + np.arange(block)) % n
    resampled = x[indices.reshape(draws, -1)[:, :n]]
    means = resampled.mean(axis=1)
    return np.quantile(means, [alpha / 2, 1 - alpha / 2], method="linear")


def ar1_paths(rng, repetitions, n, rho, sigma=0.01, mu=0.0002):
    repetitions = integer(repetitions, 1)
    n = integer(n, 2)
    if not np.isfinite([rho, sigma, mu]).all() or abs(rho) >= 1 or sigma <= 0:
        raise ValueError("stationary rho, positive marginal sigma and finite mu required")
    x = np.empty((repetitions, n))
    x[:, 0] = mu + sigma * rng.standard_normal(repetitions)
    innovation_sd = sigma * np.sqrt(1 - rho * rho)
    for t in range(1, n):
        x[:, t] = mu + rho * (x[:, t - 1] - mu) + innovation_sd * rng.standard_normal(repetitions)
    return x


def ar1_mean_variance(n, rho, sigma=0.01):
    n = integer(n, 2)
    if not np.isfinite([rho, sigma]).all() or abs(rho) >= 1 or sigma <= 0:
        raise ValueError("invalid AR(1) parameters")
    h = np.arange(1, n)
    return float(sigma * sigma / n * (1 + 2 * np.sum((1 - h / n) * rho ** h)))


def coverage_record(intervals, truth):
    intervals = np.asarray(intervals)
    covered = (intervals[:, 0] <= truth) & (truth <= intervals[:, 1])
    rate = float(covered.mean())
    return {"covered": int(covered.sum()), "repetitions": len(covered),
            "coverage": rate, "mc_se": float(np.sqrt(rate * (1 - rate) / len(covered))),
            "mean_width": float(np.mean(intervals[:, 1] - intervals[:, 0]))}


def experiment(seed=20261022, repetitions=1000):
    integer(repetitions, 2)
    integer(seed, 0)
    children = np.random.SeedSequence(seed).spawn(6)
    rngs = [np.random.Generator(np.random.PCG64(s)) for s in children]
    n, mu, sigma, alpha, lag, block, draws = 240, 0.0002, 0.01, 0.05, 12, 12, 399
    z = stats.norm.ppf(1 - alpha / 2)
    results, first_paths = {}, []
    for j, rho in enumerate((0.0, 0.6)):
        paths = ar1_paths(rngs[2 * j], repetitions, n, rho, sigma, mu)
        first_paths.append(paths[0])
        oracle_se = np.sqrt(ar1_mean_variance(n, rho, sigma))
        intervals = {name: [] for name in ("iid_t", "oracle_z", "hac_z", "block_percentile")}
        for x in paths:
            center = float(x.mean())
            intervals["iid_t"].append(mean_t(x, alpha=alpha)["ci"])
            intervals["oracle_z"].append([center - z * oracle_se, center + z * oracle_se])
            se = hac_se(x, lag)
            intervals["hac_z"].append([center - z * se, center + z * se])
            intervals["block_percentile"].append(circular_bootstrap_ci(x, rngs[2 * j + 1], block, draws, alpha))
        results[str(rho)] = {key: coverage_record(value, mu) for key, value in intervals.items()}
    rare = {}
    for method in ("wald", "wilson", "exact"):
        bounds = np.array([proportion_ci(k, 100, method=method) for k in range(101)])
        mass = stats.binom.pmf(np.arange(101), 100, 0.01)
        contains = (bounds[:, 0] <= 0.01) & (0.01 <= bounds[:, 1])
        rare[method] = float(np.sum(mass[contains]))
    # Separate artificial panel: same dates across columns; never shuffle columns separately.
    corr = np.full((4, 4), 0.3)
    np.fill_diagonal(corr, 1.0)
    panel = rngs[4].standard_normal((n, 4)) @ np.linalg.cholesky(corr).T
    panel = panel * np.array([0.01, 0.003, 0.008, 0.005])
    panel += np.array([0.0002, 0.0, -0.0001, 0.0])
    tests = [mean_t(panel[:, j]) for j in range(4)]
    raw = np.array([t["p_two_sided"] for t in tests])
    panel_report = {a: {**t, "p_bonferroni": float(b), "p_bh": float(h), "p_by": float(y)}
                    for a, t, b, h, y in zip(ASSETS, tests, adjust_p(raw, "bonferroni"),
                                            adjust_p(raw, "bh"), adjust_p(raw, "by"))}
    null_p = rngs[5].random((10000, 20))
    multiplicity = {}
    for name, rejection in (("unadjusted", np.any(null_p <= .05, axis=1)),
                            ("bonferroni", np.any(null_p <= .05 / 20, axis=1))):
        rate = float(rejection.mean())
        multiplicity[name] = {"fwer": rate, "mc_se": float(np.sqrt(rate * (1-rate) / 10000))}
    report = {"source": "SYNTHETIC", "seed": seed, "spawn_keys": [list(s.spawn_key) for s in children],
              "config": {"n": n, "mu": mu, "marginal_sigma": sigma, "alpha": alpha,
                         "lag": lag, "block": block, "bootstrap_draws": draws,
                         "repetitions": repetitions},
              "coverage": results, "binomial_exact_coverage_n100_p001": rare,
              "panel_tests": panel_report, "all_null_fwer": multiplicity,
              "limitations": "Artificial fixed-window experiments; not PIT ingestion, market validation or online alerts."}
    return report, panel, np.array(first_paths)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--repetitions", type=int, default=1000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report, panel, first_paths = experiment(args.seed, args.repetitions)
    out = args.out or Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    np.savez(out / "samples.npz", panel=panel, first_paths=first_paths, assets=np.array(ASSETS))
    report["environment"] = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    report["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["samples_sha256"] = hashlib.sha256((out / "samples.npz").read_bytes()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "coverage": report["coverage"], "rare": report["binomial_exact_coverage_n100_p001"],
                      "fwer": report["all_null_fwer"]}, indent=2))


if __name__ == "__main__":
    main()
