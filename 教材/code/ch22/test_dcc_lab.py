import unittest

import numpy as np

from correlation_lab import samples
from dcc_lab import TRAIN, fit, replay, gaussian_score


class DCCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = 100 * samples()
        cls.model = fit(data[:TRAIN])
        cls.future = data[TRAIN:]
        cls.scored = replay(cls.model, cls.future)

    def test_forecast_precedes_current_return(self):
        modified = self.future.copy()
        modified[5] += 5
        result = replay(self.model, modified)
        self.assertEqual(self.scored[:5], result[:5])
        self.assertEqual(self.scored[5]["matrices"], result[5]["matrices"])
        self.assertNotEqual(self.scored[5]["scores"], result[5]["scores"])

    def test_positive_definite_and_equal_coverage(self):
        self.assertEqual(sum(r["scores"] is not None for r in self.scored), 119)
        self.assertIsNone(self.scored[165-TRAIN]["scores"])
        for row in self.scored:
            for covariance in row["matrices"].values():
                self.assertGreater(np.linalg.eigvalsh(covariance).min(), 0)

    def test_cholesky_score(self):
        self.assertAlmostEqual(gaussian_score(np.array([1., 2.]), np.diag([1., 4.])),
                               np.log(4) + 2)

    def test_parameter_constraints(self):
        self.assertTrue(np.all(self.model["garch"][:, 0] > 0))
        self.assertTrue(np.all(self.model["garch"][:, 1:].sum(axis=1) < 1))
        self.assertLess(self.model["dcc"].sum(), 1)


if __name__ == "__main__":
    unittest.main()
