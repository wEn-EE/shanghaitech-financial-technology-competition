import math
import unittest
import numpy as np
from probability_lab import (posterior_from_loglikelihood, gaussian_logpdf, synthetic_model,
                             simulate_mixture, mixture_moments, exact_loss_tail)


class ProbabilityChecks(unittest.TestCase):
    def test_base_rate_and_duplicate(self):
        prior, log_like = [.99, .01], np.log([[.05, .9]])
        once = posterior_from_loglikelihood(prior, log_like)[0, 1]
        wrong = posterior_from_loglikelihood(prior, 2 * log_like)[0, 1]
        self.assertAlmostEqual(once, 2 / 13)
        self.assertAlmostEqual(wrong, 36 / 47)
        self.assertGreater(wrong, once)

    def test_log_normalization_is_stable(self):
        ell = np.array([[-10001., -10000.], [-20000., -20002.]])
        a = posterior_from_loglikelihood([.7, .3], ell)
        b = posterior_from_loglikelihood([.7, .3], ell + 10000)
        np.testing.assert_allclose(a, b)
        np.testing.assert_allclose(a.sum(axis=1), 1)
        self.assertTrue(np.all((a >= 0) & (a <= 1)))

    def test_invalid_probability_and_zero_evidence(self):
        for p in [[.2, .2], [-.1, 1.1], [np.nan, 1]]:
            with self.assertRaises(ValueError):
                posterior_from_loglikelihood(p, np.zeros((1, 2)))
        with self.assertRaises(ValueError):
            posterior_from_loglikelihood([1, 0], [[-np.inf, 0]])
        with self.assertRaises(ValueError):
            posterior_from_loglikelihood([.5, .5], [[np.inf, 0]])

    def test_identical_states_and_zero_prior(self):
        x = np.array([[.1, .2], [1., -1.]])
        likelihood = gaussian_logpdf(x, [0, 0], np.eye(2))
        posterior = posterior_from_loglikelihood([.8, .2], np.column_stack([likelihood] * 2))
        np.testing.assert_allclose(posterior, [[.8, .2]] * 2)
        np.testing.assert_allclose(posterior_from_loglikelihood([1, 0], [[-2, -1]]), [[1, 0]])

    def test_gaussian_density_matches_independent_formula(self):
        x = np.array([[1., 2.], [0, 0]])
        values = gaussian_logpdf(x, [0, 0], np.diag([1., 4.]))
        reference = -math.log(2 * math.pi) - math.log(2) - .5 * (x[:, 0] ** 2 + x[:, 1] ** 2 / 4)
        np.testing.assert_allclose(values, reference)

    def test_invalid_covariance(self):
        for s in [np.ones((2, 2)), [[1, 2], [2, 1]], [[1, .1], [0, 1]]]:
            with self.assertRaises((ValueError, np.linalg.LinAlgError)):
                gaussian_logpdf([[0, 0]], [0, 0], s)
        with self.assertRaises(ValueError):
            gaussian_logpdf([[np.nan]], [0], [[1]])

    def test_total_covariance_includes_between_state_term(self):
        p = [.75, .25]
        means = np.array([[0, 0], [2, -1]])
        covariances = np.array([np.eye(2), 2 * np.eye(2)])
        mean, covariance = mixture_moments(p, means, covariances)
        np.testing.assert_allclose(mean, [.5, -.25])
        np.testing.assert_allclose(covariance, [[2, -.375], [-.375, 1.4375]])

    def test_seeded_simulation_and_hidden_invalid_state(self):
        p, mu, s = synthetic_model()
        a = simulate_mixture(np.random.default_rng(19), 400, p, mu, s)
        b = simulate_mixture(np.random.default_rng(19), 400, p, mu, s)
        np.testing.assert_array_equal(a[0], b[0])
        np.testing.assert_array_equal(a[1], b[1])
        self.assertEqual(a[1].shape, (400, 4))
        broken = s.copy()
        broken[1] = 0
        with self.assertRaises(np.linalg.LinAlgError):
            simulate_mixture(np.random.default_rng(19), 10, [1, 0], mu, broken)

    def test_normal_tail_reference_and_weighted_mixture(self):
        p = np.array([.8, .2])
        mu = np.array([[0.], [-1.]])
        s = np.array([[[1.]], [[4.]]])
        expected = .8 * .5 * math.erfc(1 / math.sqrt(2)) + .2 * .5
        self.assertAlmostEqual(exact_loss_tail(p, mu, s, [1], 1), expected)

    def test_state_reordering_preserves_inference(self):
        p, mu, s = synthetic_model()
        x = np.array([[.001, .001, 0, 0], [-.04, .01, .02, -.01]])
        ell = np.column_stack([gaussian_logpdf(x, mu[k], s[k]) for k in range(2)])
        original = posterior_from_loglikelihood(p, ell)
        permuted = posterior_from_loglikelihood(p[::-1], ell[:, ::-1])
        np.testing.assert_allclose(original, permuted[:, ::-1])

    def test_mc_tail_has_expected_sampling_scale(self):
        p, mu, s = synthetic_model()
        count, w = 80000, np.array([.4, .25, .2, .15])
        _, returns = simulate_mixture(np.random.default_rng(81), count, p, mu, s)
        estimate = np.mean(-(returns @ w) > .02)
        exact = exact_loss_tail(p, mu, s, w, .02)
        # 固定种子的统计健全性检查，不是所有随机抽样都会落在界内的证明。
        self.assertLess(abs(estimate - exact), 6 * math.sqrt(exact * (1 - exact) / count))

    def test_simulation_rejects_invalid_count_and_parameters(self):
        p, mu, s = synthetic_model()
        for count in [0, -1, 1.5, True]:
            with self.assertRaises(ValueError):
                simulate_mixture(np.random.default_rng(1), count, p, mu, s)
        with self.assertRaises(ValueError):
            mixture_moments(p, mu[:, :2], s)
        with self.assertRaises(ValueError):
            exact_loss_tail(p, mu, s, [0, 0, 0, 0], .02)


if __name__ == "__main__":
    unittest.main()
