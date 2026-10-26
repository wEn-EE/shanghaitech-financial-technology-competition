import unittest
import numpy as np
import statsmodels.api as sm
from statsmodels.stats.sandwich_covariance import cov_hac
from pricing_lab import fit, hac_cov, prefit, attribute, sdf_example, generate


class PricingTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(14)
        self.f = rng.normal(size=(100, 2))
        self.y = self.f @ np.array([[1., -.2], [.6, .4]]) + rng.normal(0, .1, (100, 2))

    def test_exact_linear_recovery(self):
        true = np.array([[.2, -.1], [1., 2.], [-.5, .3]])
        y = np.column_stack([np.ones(100), self.f]) @ true
        b, residual, _ = fit(self.f, y)
        np.testing.assert_allclose(b, true, atol=1e-14)
        np.testing.assert_allclose(residual, 0, atol=1e-14)

    def test_projection_orthogonality(self):
        _, u, _ = fit(self.f, self.y)
        x = sm.add_constant(self.f)
        np.testing.assert_allclose(x.T @ u, 0, atol=1e-12)

    def test_hac_external_reference(self):
        _, u, _ = fit(self.f, self.y)
        reference = sm.OLS(self.y[:, 0], sm.add_constant(self.f)).fit()
        for lag in [0, 5]:
            np.testing.assert_allclose(hac_cov(self.f, u[:, 0], lag),
                                       cov_hac(reference, nlags=lag, use_correction=True),
                                       rtol=1e-10, atol=1e-12)

    def test_factor_unit_invariance(self):
        b, u, _ = fit(self.f, self.y)
        b2, u2, _ = fit(self.f*100, self.y)
        np.testing.assert_allclose(b[1:], b2[1:]*100)
        np.testing.assert_allclose(u, u2, atol=1e-13)

    def test_future_does_not_change_prefit(self):
        old = prefit(self.f, self.y, 40, 20)
        f, y = self.f.copy(), self.y.copy()
        f[70:] += 10
        y[70:] -= 20
        new = prefit(f, y, 40, 20)
        for a, b in zip(old, new):
            np.testing.assert_array_equal(a[:31], b[:31])
        self.assertFalse(np.array_equal(old[0][31:], new[0][31:]))

    def test_late_training_rejected(self):
        available = np.arange(100)+.1
        available[39] = 40.1
        with self.assertRaises(ValueError):
            prefit(self.f, self.y, 40, 20, available)

    def test_current_factor_not_early(self):
        b = fit(self.f, self.y)[0]
        with self.assertRaises(ValueError):
            attribute(b, self.f[0], self.y[0], .1, -.2)

    def test_attribution_accounting(self):
        b = fit(self.f, self.y)[0]
        c, r = attribute(b, self.f[0], self.y[0], .1, .2)
        np.testing.assert_allclose(c.sum(axis=0)+r, self.y[0])

    def test_bad_data_and_rank_rejected(self):
        with self.assertRaises(ValueError):
            fit(np.column_stack([self.f[:, 0]]*2), self.y)
        bad = self.y.copy()
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            fit(self.f, bad)
        with self.assertRaises(ValueError):
            hac_cov(self.f, np.ones(100), -1)

    def test_omitted_factor_intercept(self):
        f1 = np.array([-1., -1., 1., 1.])
        f2 = .02 + .3*f1 + np.array([1., -1., 1., -1.])
        y = (1.1*f1 + .8*f2)[:, None]
        one = fit(f1[:, None], y)[0]
        two = fit(np.column_stack([f1, f2]), y)[0]
        np.testing.assert_allclose(one[:, 0], [.016, 1.34], atol=1e-13)
        self.assertAlmostEqual(two[0, 0], 0)

    def test_sdf_state_prices_and_premia(self):
        r = sdf_example()
        np.testing.assert_allclose(r['prices'], [.95, 92., 98.])
        np.testing.assert_allclose(r['euler_errors'], 0, atol=1e-14)
        self.assertGreater(r['expected_excess'][1], 0)
        self.assertLess(r['expected_excess'][2], 0)

    def test_dgp_reproducibility(self):
        for a, b in zip(generate(), generate()):
            np.testing.assert_array_equal(a, b)


if __name__ == '__main__':
    unittest.main()
