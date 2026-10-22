"""第3章：线性代数金融实验；仅使用既有NumPy与pandas。"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd


def finite_matrix(value, name, min_rows=1):
    x = np.array(value, dtype=np.float64, copy=True, order="C")
    if x.ndim != 2 or x.shape[0] < min_rows or x.shape[1] == 0:
        raise ValueError(f"{name}: invalid two-dimensional shape")
    if not np.isfinite(x).all():
        raise ValueError(f"{name}: non-finite entries require an explicit data policy")
    return x


def fit_factors(factors, returns, rcond=1e-12):
    f = finite_matrix(factors, "factors", min_rows=2)
    y = finite_matrix(returns, "returns", min_rows=2)
    if len(f) != len(y):
        raise ValueError("factor and return rows must match")
    design = np.column_stack([np.ones(len(f)), f])
    coef, _, rank, singular = np.linalg.lstsq(design, y, rcond=rcond)
    residual = y - design @ coef
    # lstsq返回的residuals可能为空，故显式计算实际残差和平方和。
    return {"coef": coef, "design": design, "residual": residual,
            "ssr": np.sum(residual ** 2, axis=0), "rank": int(rank),
            "singular": singular, "condition": float(np.linalg.cond(design))}


def sample_covariance(values):
    x = finite_matrix(values, "covariance input", min_rows=2)
    centered = x - x.mean(axis=0)
    return centered.T @ centered / (len(x) - 1)


def shrink_covariance(covariance, alpha=0.1, tolerance=1e-10):
    s = finite_matrix(covariance, "covariance")
    if s.shape[0] != s.shape[1] or not np.isfinite(alpha) or not 0 < alpha <= 1:
        raise ValueError("square covariance and 0 < alpha <= 1 required")
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be finite and positive")
    scale = max(float(np.linalg.norm(s, ord=2)), np.finfo(float).tiny)
    if np.max(np.abs(s - s.T)) > tolerance * scale:
        raise ValueError("materially asymmetric covariance")
    # 仅消除已通过容差检查的浮点非对称，不修补显著负特征值。
    s = (s + s.T) / 2
    if np.linalg.eigvalsh(s)[0] < -tolerance * scale:
        raise ValueError("materially indefinite covariance; inspect data construction")
    tau = float(np.trace(s) / len(s))
    if tau <= 0:
        raise ValueError("zero average variance needs a separate policy")
    regularized = (1 - alpha) * s + alpha * tau * np.eye(len(s))
    np.linalg.cholesky(regularized)
    return regularized


def fit_pca(values, components=2):
    x = finite_matrix(values, "PCA input", min_rows=2)
    mean = x.mean(axis=0)
    centered = x - mean
    _, singular, vh = np.linalg.svd(centered, full_matrices=False)
    tolerance = np.finfo(float).eps * max(centered.shape) * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    if (isinstance(components, bool) or not isinstance(components, (int, np.integer))
            or not 1 <= components <= rank):
        raise ValueError("components must be an integer within numerical rank")
    directions = vh[:components].T.copy()
    # 固定单列符号便于展示；重根下的子空间旋转仍然不唯一。
    for j in range(components):
        anchor = np.argmax(np.abs(directions[:, j]))
        if directions[anchor, j] < 0:
            directions[:, j] *= -1
    eigenvalues = singular ** 2 / (len(x) - 1)
    return {"mean": mean, "directions": directions, "eigenvalues": eigenvalues,
            "ratio": eigenvalues / eigenvalues.sum(), "rank": rank}


def project_pca(values, model):
    x = finite_matrix(values, "PCA transform")
    if x.shape[1] != len(model["mean"]):
        raise ValueError("asset columns must match the fitted model")
    centered = x - model["mean"]
    scores = centered @ model["directions"]
    reconstructed = scores @ model["directions"].T + model["mean"]
    error = np.sum((x - reconstructed) ** 2, axis=1)
    return scores, reconstructed, error


def squared_distance(values, mean, covariance):
    x = finite_matrix(values, "distance input")
    mean = np.asarray(mean, dtype=float)
    s = finite_matrix(covariance, "distance covariance")
    if mean.shape != (x.shape[1],) or not np.isfinite(mean).all():
        raise ValueError("mean shape or finiteness mismatch")
    if s.shape != (x.shape[1], x.shape[1]) or not np.allclose(s, s.T, rtol=0, atol=1e-15):
        raise ValueError("distance requires a symmetric matching covariance")
    lower = np.linalg.cholesky(s)
    whitened = np.linalg.solve(lower, (x - mean).T)
    return np.sum(whitened ** 2, axis=0)


def demo_data():
    growth = 0.01 * np.array([-1, -1, -1, -1, 1, 1, 1, 1])
    rates = 0.005 * np.array([-1, -1, 1, 1, -1, -1, 1, 1])
    f_train = np.column_stack([growth, rates])
    f_test = np.array([[.03, 0], [-.02, .01], [0, -.015], [.025, .015]])
    factors = np.vstack([f_train, f_test])
    alpha = np.array([.0002, .0001, 0, -.0001])
    beta = np.array([[1.2, -.3, .5, .1], [-.4, -1.5, .2, 1.]])
    noise_direction = np.array([1., .6, -.8, .4])
    noise_time = .001 * np.array([-1, 1, -1, 1, -1, 1, -1, 1, 1, -1, 2, -2])
    returns = alpha + factors @ beta + noise_time[:, None] * noise_direction
    index = pd.date_range("2025-01-06T01:30:00Z", periods=12, freq="min")
    names = ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"]
    return (pd.DataFrame(factors, index=index, columns=["growth_proxy", "rates_proxy"]),
            pd.DataFrame(returns, index=index, columns=names), alpha, beta)


def pairwise_counterexample():
    # 不同资产对使用互不相同的重叠样本；保留原始缺失结构。
    return pd.DataFrame({"A": [-1, 1, -1, 1, np.nan, np.nan],
                         "B": [-1, 1, np.nan, np.nan, -1, 1],
                         "C": [np.nan, np.nan, -1, 1, 1, -1]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or Path(__file__).parent / "runs" / datetime.now(
        timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    factors, returns, alpha, beta = demo_data()
    factors.to_csv(output / "synthetic_factors.csv")
    returns.to_csv(output / "synthetic_returns.csv")
    training = returns.iloc[:8]
    evaluation = returns.iloc[8:]
    factor_fit = fit_factors(factors.iloc[:8], training)
    q, r = np.linalg.qr(factor_fit["design"], mode="reduced")
    coef_qr = np.linalg.solve(r, q.T @ training.to_numpy())
    pca = fit_pca(training, components=2)
    scores, reconstructed, error = project_pca(evaluation, pca)
    covariance = sample_covariance(training)
    shrunk = shrink_covariance(covariance, alpha=0.1)
    distance = squared_distance(evaluation, pca["mean"], shrunk)
    pairwise = pairwise_counterexample()
    pairwise.to_csv(output / "pairwise_raw.csv", index=False)
    pair_correlation = pairwise.corr()
    pair_correlation.to_csv(output / "pairwise_correlation.csv")
    for name, values in {"covariance": covariance, "shrunk_covariance": shrunk}.items():
        pd.DataFrame(values, index=returns.columns, columns=returns.columns).to_csv(output / f"{name}.csv")
    pd.DataFrame(factor_fit["coef"], index=["intercept", *factors.columns],
                 columns=returns.columns).to_csv(output / "factor_coefficients.csv")
    pd.DataFrame(scores, index=evaluation.index, columns=["PC1", "PC2"]).to_csv(output / "scores.csv")
    pd.DataFrame(reconstructed, index=evaluation.index, columns=returns.columns).to_csv(output / "reconstructed.csv")
    pd.DataFrame({"reconstruction_error": error, "squared_distance": distance},
                 index=evaluation.index).to_csv(output / "diagnostics.csv")
    np.savez(output / "training_basis.npz", mean=pca["mean"], directions=pca["directions"],
             eigenvalues=pca["eigenvalues"], covariance=shrunk,
             asset_order=np.array(returns.columns, dtype=str))
    report = {"data_kind": "synthetic", "numpy": np.__version__, "pandas": pd.__version__,
              "train_rows": 8, "evaluation_rows": 4, "train_end": training.index[-1].isoformat(),
              "asset_order": returns.columns.tolist(), "factor_order": factors.columns.tolist(),
              "rcond": 1e-12, "shrinkage_alpha": 0.1,
              "factor_design_rank": factor_fit["rank"],
              "coefficient_max_abs_error_vs_generator": float(np.max(np.abs(
                  factor_fit["coef"] - np.vstack([alpha, beta])))),
              "qr_lstsq_max_abs_difference": float(np.max(np.abs(coef_qr - factor_fit["coef"]))),
              "pca_numerical_rank": pca["rank"], "pca_top2_variance_ratio": float(pca["ratio"][:2].sum()),
              "covariance_eigenvalues": np.linalg.eigvalsh(covariance).tolist(),
              "shrunk_eigenvalues": np.linalg.eigvalsh(shrunk).tolist(),
              "pairwise_correlation_eigenvalues": np.linalg.eigvalsh(pair_correlation).tolist(),
              "interpretation": "numerical demonstrations; no empirical market performance claim"}
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                     allow_nan=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    print(f"Artifacts: {output.resolve()}")


if __name__ == "__main__":
    main()
