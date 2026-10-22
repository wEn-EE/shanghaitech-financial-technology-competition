import unittest
import numpy as np
import pandas as pd
from linear_lab import (demo_data, fit_factors, sample_covariance, shrink_covariance,
                        fit_pca, project_pca, squared_distance, pairwise_counterexample)


class LinearTests(unittest.TestCase):
    def setUp(self):
        self.f, self.y, self.alpha, self.beta = demo_data()
        self.train = self.y.iloc[:8]

    def test_factor_recovery_and_orthogonal_residual(self):
        fitted = fit_factors(self.f.iloc[:8], self.train)
        np.testing.assert_allclose(fitted["coef"], np.vstack([self.alpha, self.beta]), atol=1e-12)
        np.testing.assert_allclose(fitted["design"].T @ fitted["residual"], 0, atol=1e-14)
        self.assertEqual(fitted["rank"], 3)

    def test_rank_deficient_coefficients_are_minimum_norm(self):
        factor = np.array([[-1.], [0.], [1.]])
        repeated = np.column_stack([factor, factor])
        fitted = fit_factors(repeated, 2 * factor)
        np.testing.assert_allclose(fitted["coef"].ravel(), [0, 1, 1], atol=1e-12)
        self.assertEqual(fitted["rank"], 2)
        np.testing.assert_allclose(fitted["ssr"], [0], atol=1e-25)

    def test_covariance_matches_reference_and_is_psd(self):
        covariance = sample_covariance(self.train)
        np.testing.assert_allclose(covariance, np.cov(self.train, rowvar=False, ddof=1), atol=1e-18)
        self.assertGreaterEqual(np.linalg.eigvalsh(covariance)[0], -1e-18)
        self.assertLessEqual(np.linalg.matrix_rank(covariance), 3)
        w = np.array([.4, .3, .2, .1])
        self.assertAlmostEqual(float(w @ covariance @ w), np.var(self.train.to_numpy() @ w, ddof=1))

    def test_shrinkage_is_positive_definite_and_rejects_bad_input(self):
        covariance = sample_covariance(self.train)
        regularized = shrink_covariance(covariance, .1)
        self.assertGreater(np.linalg.eigvalsh(regularized)[0], 0)
        np.linalg.cholesky(regularized)
        with self.assertRaises(ValueError):
            shrink_covariance(np.array([[1., 2.], [2., 1.]]))
        with self.assertRaises(ValueError):
            shrink_covariance(np.zeros((2, 2)))

    def test_pca_matches_covariance_eigenvalues(self):
        model = fit_pca(self.train, 2)
        np.testing.assert_allclose(model["directions"].T @ model["directions"], np.eye(2), atol=1e-12)
        eigenvalues = np.linalg.eigvalsh(sample_covariance(self.train))[::-1]
        np.testing.assert_allclose(model["eigenvalues"], eigenvalues, atol=1e-18)
        eigval, eigvec = np.linalg.eigh(sample_covariance(self.train))
        reference = eigvec[:, np.argsort(eigval)[::-1][:2]]
        np.testing.assert_allclose(model["directions"] @ model["directions"].T,
                                   reference @ reference.T, atol=1e-12)

    def test_reconstruction_energy_and_monotonicity(self):
        errors = []
        for k in (1, 2, 3):
            model = fit_pca(self.train, k)
            _, reconstructed, error = project_pca(self.train, model)
            expected = (len(self.train)-1) * model["eigenvalues"][k:].sum()
            self.assertAlmostEqual(error.sum(), expected)
            errors.append(error.sum())
        self.assertGreaterEqual(errors[0], errors[1])
        self.assertGreaterEqual(errors[1], errors[2])

    def test_future_values_do_not_change_training_basis(self):
        changed = self.y.copy()
        changed.iloc[8:] = changed.iloc[8:] + 100
        np.testing.assert_array_equal(self.y.iloc[:8], changed.iloc[:8])
        old = fit_pca(self.y.iloc[:8], 2)
        new = fit_pca(changed.iloc[:8], 2)
        np.testing.assert_array_equal(old["mean"], new["mean"])
        np.testing.assert_array_equal(old["directions"], new["directions"])
        frozen_mean = old["mean"].copy()
        project_pca(changed.iloc[8:], old)
        np.testing.assert_array_equal(old["mean"], frozen_mean)

    def test_pairwise_correlation_is_indefinite(self):
        correlation = pairwise_counterexample().corr().to_numpy()
        np.testing.assert_allclose(np.linalg.eigvalsh(correlation), [-1, 2, 2], atol=1e-12)
        w = np.array([-1, 1, 1]) / np.sqrt(3)
        self.assertAlmostEqual(float(w @ correlation @ w), -1)
        with self.assertRaises(ValueError):
            shrink_covariance(correlation)

    def test_distance_matches_solve_and_is_nonnegative(self):
        model = fit_pca(self.train, 2)
        covariance = shrink_covariance(sample_covariance(self.train))
        values = self.y.iloc[8:].to_numpy()
        delta = values-model["mean"]
        reference = np.sum(delta * np.linalg.solve(covariance, delta.T).T, axis=1)
        actual = squared_distance(values, model["mean"], covariance)
        np.testing.assert_allclose(actual, reference, rtol=1e-12)
        self.assertTrue((actual >= 0).all())

    def test_nonfinite_zero_variance_and_shape_fail_explicitly(self):
        for values in (np.array([[1., np.nan], [2, 3]]), np.array([[1., np.inf], [2, 3]])):
            with self.assertRaises(ValueError):
                sample_covariance(values)
        with self.assertRaises(ValueError):
            fit_pca(np.ones((4, 2)), 1)
        with self.assertRaises(ValueError):
            fit_factors([[1], [2]], [[1, 2]])
        with self.assertRaises(ValueError):
            project_pca([[1, 2]], fit_pca(self.train, 2))

    def test_near_collinearity_amplifies_coefficient_perturbations(self):
        t = np.linspace(-1, 1, 8)
        z = np.array([-1, 1, -1, 1, -1, 1, -1, 1])
        factors = np.column_stack([t, t + 1e-8*z])
        y = (.0005 + .02*t)[:, None]
        before = fit_factors(factors, y)
        after = fit_factors(factors, y + (1e-6*z)[:, None])
        self.assertGreater(before["condition"], 1e7)
        self.assertGreater(np.linalg.norm(after["coef"]-before["coef"]), 100)
        change = before["design"] @ (after["coef"]-before["coef"])
        self.assertLess(np.max(np.abs(change)), 2e-6)


if __name__ == "__main__":
    unittest.main()
