import unittest
import numpy as np
from scipy import stats
from inference_lab import (mean_t, proportion_ci, adjust_p, hac_se, circular_bootstrap_ci,
                           ar1_paths, ar1_mean_variance, coverage_record)


class InferenceTests(unittest.TestCase):
    def test_t_against_scipy(self):
        x = np.array([.01, -.02, .03, .015, -.005])
        ours = mean_t(x, .002)
        reference = stats.ttest_1samp(x, .002)
        self.assertAlmostEqual(ours["t"], reference.statistic)
        self.assertAlmostEqual(ours["p_two_sided"], reference.pvalue)

    def test_t_translation_and_scale(self):
        x = np.array([1., 2., 4., 8.])
        a, b = mean_t(x, 3), mean_t(7 + 10 * x, 37)
        self.assertAlmostEqual(a["t"], b["t"])
        np.testing.assert_allclose(b["ci"], 7 + 10 * np.array(a["ci"]))

    def test_reject_missing_and_degenerate(self):
        for x in ([1], [1, np.nan], [1, np.inf], [1, 1], [[1, 2]]):
            with self.assertRaises(ValueError):
                mean_t(x)

    def test_binomial_intervals_against_scipy(self):
        for n in (1, 10, 100):
            for k in (0, n // 2, n):
                for method in ("wilson", "exact"):
                    ref = stats.binomtest(k, n).proportion_ci(.95, method=method)
                    np.testing.assert_allclose(proportion_ci(k, n, method=method),
                                               [ref.low, ref.high], atol=1e-12)

    def test_zero_counts_and_invalid(self):
        self.assertEqual(proportion_ci(0, 100, method="wald"), (0., 0.))
        self.assertGreater(proportion_ci(0, 100)[1], 0)
        self.assertEqual(proportion_ci(0, 100)[0], 0.0)
        self.assertEqual(proportion_ci(100, 100)[1], 1.0)
        for k, n in ((1.5, 10), (-1, 10), (11, 10), (0, 0), (True, 10)):
            with self.assertRaises(ValueError):
                proportion_ci(k, n)

    def test_adjustments_against_scipy(self):
        p = np.array([.8, .003, .021, .04, .003, 1., 0.])
        for method in ("bh", "by"):
            np.testing.assert_allclose(adjust_p(p, method),
                                       stats.false_discovery_control(p, method=method))

    def test_adjustment_order_and_invalid(self):
        p = np.array([.032, .001, .018, .21])
        np.testing.assert_allclose(adjust_p(p), [.0426666666667, .004, .036, .21])
        for x in ([], [-.1], [np.nan], [1.01], [[.1, .2]]):
            with self.assertRaises(ValueError):
                adjust_p(x)

    def test_hac_bartlett_quadratic_form(self):
        x = np.array([.1, .3, -.2, .15, .2])
        lag = 2
        residual = x - x.mean()
        distance = np.abs(np.arange(len(x))[:, None] - np.arange(len(x))[None, :])
        kernel = np.maximum(1 - distance / (lag + 1), 0)
        expected = residual @ kernel @ residual / len(x) ** 2
        self.assertAlmostEqual(hac_se(x, lag) ** 2, expected)

    def test_hac_zero_lag_and_invalid(self):
        x = np.array([1., 3., 2., 5.])
        self.assertAlmostEqual(hac_se(x, 0) ** 2, x.var(ddof=0) / len(x))
        for lag in (-1, len(x), 1.5):
            with self.assertRaises(ValueError):
                hac_se(x, lag)

    def test_ar1_oracle_covariance_sum(self):
        for rho in (-.5, 0., .6):
            n, sigma = 11, .02
            h = np.abs(np.arange(n)[:, None] - np.arange(n)[None, :])
            covariance = sigma ** 2 * rho ** h
            self.assertAlmostEqual(ar1_mean_variance(n, rho, sigma), covariance.sum() / n**2)

    def test_ar1_stationarity_and_reproduction(self):
        a = ar1_paths(np.random.default_rng(42), 20000, 5, .6)
        b = ar1_paths(np.random.default_rng(42), 20000, 5, .6)
        np.testing.assert_array_equal(a, b)
        self.assertLess(abs(a[:, 0].var() / .01**2 - 1), .04)
        self.assertLess(abs(a[:, -1].var() / .01**2 - 1), .04)

    def test_bootstrap_block_semantics(self):
        x = np.arange(12.)
        # Full circular blocks only rotate the data, so the mean cannot vary.
        ci = circular_bootstrap_ci(x, np.random.default_rng(1), block=12, draws=100)
        np.testing.assert_allclose(ci, [x.mean(), x.mean()])
        a = circular_bootstrap_ci(x, np.random.default_rng(2), block=1, draws=100)
        b = circular_bootstrap_ci(x, np.random.default_rng(2), block=1, draws=100)
        np.testing.assert_array_equal(a, b)
        self.assertGreater(a[1] - a[0], 0)
        with self.assertRaises(ValueError):
            circular_bootstrap_ci(x, np.random.default_rng(2), block=13)

    def test_coverage_closed_endpoints(self):
        record = coverage_record([[0, 1], [1, 2], [2, 3]], 1)
        self.assertEqual(record["covered"], 2)
        self.assertAlmostEqual(record["coverage"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
