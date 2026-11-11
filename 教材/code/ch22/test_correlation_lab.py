import unittest
import numpy as np
from correlation_lab import covariance, correlation, shrink, dcc_step, pairwise_example, samples, replay


class Tests(unittest.TestCase):
    def test_covariance_reference(self):
        x = samples(60)
        np.testing.assert_allclose(covariance(x), np.cov(x, rowvar=False))
    def test_singular_shrink(self):
        s = covariance(np.array([[1, 2, 3], [2, 4, 6], [3, 6, 9.]]))
        self.assertLess(abs(np.linalg.eigvalsh(s)[0]), 1e-12)
        self.assertGreater(np.linalg.eigvalsh(shrink(s))[0], 0)
    def test_invalid_pairwise(self):
        _, r = pairwise_example()
        np.testing.assert_allclose(np.linalg.eigvalsh(r), [-1, 2, 2])
        self.assertLess(np.array([-1, 1, 1]) @ r @ np.array([-1, 1, 1]), 0)
    def test_prefix(self):
        a = replay(samples())
        b = replay(samples(140))
        self.assertEqual(a["records"][:80], b["records"])
    def test_future_mutation(self):
        x = samples()
        a = replay(x)
        x[200:] = 999
        self.assertEqual(a["records"][:140], replay(x)["records"][:140])
    def test_forecast_order(self):
        x = samples()
        a = replay(x)
        x[100] *= 100
        b = replay(x)
        self.assertEqual(a["records"][40]["forecast_cov"], b["records"][40]["forecast_cov"])
        self.assertNotEqual(a["records"][40]["updated_cov"], b["records"][40]["updated_cov"])
    def test_missing_and_psd(self):
        rows = replay(samples())["records"]
        r = rows[105]
        self.assertFalse(r["updated"])
        self.assertEqual(r["last_update"], 164)
        self.assertEqual(r["n_complete"], 39)
        self.assertNotIn(165, r["complete_ids"])
        for row in rows:
            h = np.array(row["updated_cov"])
            self.assertGreater(np.linalg.eigvalsh(h)[0], 0)
            np.testing.assert_allclose(np.diag(correlation(h)), 1)
    def test_dcc_and_boundary(self):
        q, r = dcc_step(np.eye(4), np.array([1., -1, 0, 2]), np.eye(4))
        self.assertGreater(np.linalg.eigvalsh(q)[0], 0)
        np.testing.assert_allclose(np.diag(r), 1)
        with self.assertRaises(ValueError):
            dcc_step(q, np.ones(4), q, 0.2, 0.9)
        with self.assertRaises(ValueError):
            correlation(np.zeros((4, 4)))


if __name__ == "__main__":
    unittest.main()
