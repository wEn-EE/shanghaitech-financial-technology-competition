import unittest
import numpy as np
from optimization_lab import (central_gradient, minimize, project_simplex, minimum_variance,
                              risk_contributions, risk_budget, synthetic_covariance, spd)


class OptimizationChecks(unittest.TestCase):
    def test_gradient_and_newton_match_closed_form(self):
        q = np.array([[4., 1.], [1., 3.]])
        c = np.array([-1., -2.])
        f = lambda x: float(.5 * x @ q @ x + c @ x)
        g = lambda x: q @ x + c
        x = np.array([2., -1.])
        np.testing.assert_allclose(central_gradient(f, x), g(x), atol=1e-8)
        for hessian in [None, lambda z: q]:
            result = minimize(f, g, x, hess=hessian)
            self.assertTrue(result["converged"])
            np.testing.assert_allclose(result["x"], np.linalg.solve(q, -c), atol=1e-8)
            values = [row["objective"] for row in result["history"]]
            self.assertTrue(np.all(np.diff(values) <= 1e-14))
            if hessian is not None:
                self.assertEqual(len(result["history"]) - 1, 1)

    def test_backtracking_and_iteration_limit(self):
        f = lambda x: float(50 * x @ x)
        g = lambda x: 100 * x
        result = minimize(f, g, [1.], max_iter=1)
        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "iteration_limit")
        self.assertLess(result["history"][0]["step"], 1)
        stopped = minimize(f, g, [1.], max_iter=0)
        self.assertFalse(stopped["converged"])

    def test_simplex_projection_certificate(self):
        v = np.array([.8, -.4, .7])
        w = project_simplex(v)
        np.testing.assert_allclose(w, [.55, 0, .45])
        self.assertAlmostEqual(w.sum(), 1)
        self.assertTrue(np.all(w >= 0))
        # 活跃坐标v_i-w_i相同；非活跃坐标不超过该阈值。
        threshold = (v - w)[w > 0][0]
        np.testing.assert_allclose((v - w)[w > 0], threshold)
        self.assertTrue(np.all(v[w == 0] <= threshold))
        np.testing.assert_allclose(project_simplex(w), w)

    def test_boundary_optimum_requires_projected_stationarity(self):
        s = np.array([[1., 2.], [2., 9.]])
        result = minimum_variance(s)
        self.assertTrue(result["converged"])
        np.testing.assert_allclose(result["x"], [1, 0], atol=1e-8)
        self.assertGreater(np.linalg.norm(s @ result["x"]), .1)
        self.assertLess(result["history"][-1]["mapping_norm"], 1e-9)

    def test_interior_minimum_variance(self):
        s = synthetic_covariance()
        result = minimum_variance(s)
        self.assertTrue(result["converged"])
        reference = np.linalg.solve(s, np.ones(4))
        reference /= reference.sum()
        self.assertTrue(np.all(reference > 0))
        np.testing.assert_allclose(result["x"], reference, atol=1e-8)

    def test_risk_budget_diagonal_solution(self):
        vol = np.array([.02, .01, .03])
        b = np.array([.5, .3, .2])
        result = risk_budget(np.diag(vol ** 2), b)
        expected = np.sqrt(b) / vol
        expected /= expected.sum()
        np.testing.assert_allclose(result["weights"], expected, atol=1e-8)
        np.testing.assert_allclose(result["relative_contributions"], b, atol=1e-8)

    def test_risk_budget_invariance_to_common_covariance_scale(self):
        s = synthetic_covariance()
        b = np.array([.4, .2, .2, .2])
        a, c = risk_budget(s, b), risk_budget(s * 1e6, b)
        np.testing.assert_allclose(a["weights"], c["weights"], atol=1e-9)
        np.testing.assert_allclose(a["relative_contributions"], b, atol=1e-9)

    def test_risk_gradient_and_hessian(self):
        c = synthetic_covariance()
        c /= np.mean(np.diag(c))
        b, x = np.full(4, .25), np.array([.5, .7, .6, .8])
        fun = lambda y: float(.5 * y @ c @ y - b @ np.log(y))
        grad = lambda y: c @ y - b / y
        hess = c + np.diag(b / x ** 2)
        np.testing.assert_allclose(central_gradient(fun, x), grad(x), atol=1e-8)
        numeric = np.column_stack([central_gradient(lambda y: grad(y)[j], x)
                                   for j in range(4)])
        np.testing.assert_allclose(hess, numeric, atol=1e-8)

    def test_euler_sum_and_negative_contribution(self):
        s = np.array([[1., -.9], [-.9, 1.]])
        w = np.array([.1, .9])
        absolute, relative = risk_contributions(w, s)
        self.assertAlmostEqual(absolute.sum(), np.sqrt(w @ s @ w))
        self.assertAlmostEqual(relative.sum(), 1)
        self.assertLess(relative[0], 0)

    def test_trapezoid_refinement(self):
        errors = []
        for count in [10, 20]:
            x = np.linspace(0, 1, count + 1)
            errors.append(np.trapezoid(x ** 2, x) - 1 / 3)
        self.assertAlmostEqual(errors[0] / errors[1], 4, places=10)

    def test_invalid_matrices_and_budgets(self):
        for s in [np.ones((2, 2)), [[1, 2], [2, 1]], [[1, .1], [0, 1]]]:
            with self.assertRaises((ValueError, np.linalg.LinAlgError)):
                spd(s)
        for b in [[.5, .5], [0, .3, .3, .4], [-.1, .3, .4, .4], [.2] * 4]:
            with self.assertRaises(ValueError):
                risk_budget(synthetic_covariance(), b)

    def test_domain_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            minimize(lambda x: float(x @ x), lambda x: 2 * x, [0], positive=True)
        with self.assertRaises(ValueError):
            project_simplex([np.nan, 1])
        with self.assertRaises(ValueError):
            central_gradient(lambda x: float(x @ x), [1], relative_step=0)


if __name__ == "__main__":
    unittest.main()

