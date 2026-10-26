import unittest
import numpy as np
from risk_lab import (covariance, second_moment, correlation, forecasts, describe,
                      aggregate_log_variance, generate_daily, sampling_experiment, CONFIG)


class RiskTests(unittest.TestCase):
    def test_covariance_crosscheck(self):
        x = np.random.default_rng(1).normal(size=(20, 4))
        np.testing.assert_allclose(covariance(x), np.cov(x, rowvar=False, ddof=1))
        w = np.array([.4, .3, .2, .1])
        self.assertAlmostEqual(w @ covariance(x) @ w, np.var(x @ w, ddof=1))

    def test_return_aggregation(self):
        r = np.array([.1, -.1])
        self.assertAlmostEqual(np.expm1(np.log1p(r).sum()), -.01)
        self.assertAlmostEqual(np.log1p(r.mean()), 0)
        self.assertLess(np.log1p(r).mean(), 0)

    def test_scaling_and_correlation(self):
        x = np.random.default_rng(2).normal(size=(30, 3))
        np.testing.assert_allclose(covariance(100*x), 10000*covariance(x))
        np.testing.assert_allclose(correlation(covariance(100*x)), correlation(covariance(x)))

    def test_multiperiod_variance(self):
        self.assertAlmostEqual(aggregate_log_variance([1, .5, .25], 3), 5.5)
        self.assertEqual(aggregate_log_variance([1, 0, 0], 3), 3)

    def test_prediction_causality(self):
        x = np.random.default_rng(3).normal(size=(100, 4))
        first, _ = forecasts(x, 40, 20)
        changed = x.copy()
        changed[70:] += 100
        other, _ = forecasts(changed, 40, 20)
        np.testing.assert_array_equal(first[:31], other[:31])
        self.assertFalse(np.array_equal(first[31:], other[31:]))

    def test_ewma_update_and_psd(self):
        x = np.random.default_rng(4).normal(size=(80, 4))
        pred, protocol = forecasts(x, 40, 20)
        np.testing.assert_allclose(pred[1, 2], .94*pred[0, 2]+.06*np.outer(x[40], x[40]))
        self.assertGreaterEqual(np.linalg.eigvalsh(pred).min(), -1e-12)
        self.assertTrue(np.all(protocol[:, 2] < protocol[:, 3]))

    def test_late_history_rejected(self):
        x = np.ones((80, 4))
        available = np.arange(80)+.1
        available[20] = 45
        with self.assertRaises(ValueError):
            forecasts(x, 40, 20, available=available)

    def test_missing_and_undefined_moments(self):
        with self.assertRaises(ValueError):
            covariance([[1, 2], [3, np.nan]])
        with self.assertRaises(ValueError):
            describe(np.ones((10, 2)))
        with self.assertRaises(ValueError):
            correlation(np.diag([1., 0.]))

    def test_pairwise_impossibility_rejected(self):
        bad = np.array([[1, 1, 1], [1, 1, -1], [1, -1, 1]])
        self.assertLess(np.linalg.eigvalsh(bad).min(), 0)
        with self.assertRaises(ValueError):
            correlation(bad)

    def test_known_zero_mean_second_moment(self):
        x = np.array([[1, 2], [-1, -2]])
        np.testing.assert_array_equal(second_moment(x), [[1, 2], [2, 4]])
        np.testing.assert_array_equal(covariance(x), 2*second_moment(x))

    def test_generator_reproducibility_and_truth(self):
        a, cov = generate_daily(np.random.default_rng(8))
        b, other = generate_daily(np.random.default_rng(8))
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(cov, other)
        self.assertEqual(a.shape, (CONFIG["days"], 4))
        self.assertTrue(np.all(cov[:CONFIG["change"], 0, 1] < 0))
        self.assertTrue(np.all(cov[CONFIG["change"]:, 0, 1] > 0))

    def test_sampling_identity_and_mc_tolerance(self):
        rows = sampling_experiment(np.random.default_rng(9))
        for row in rows:
            self.assertEqual(row["increments"]*row["stride"], CONFIG["intraday_steps"])
            self.assertLess(abs(row["noisy_mean"]-row["expected_noisy"]),
                            6*row["noisy_mc_se"])


if __name__ == "__main__":
    unittest.main()
