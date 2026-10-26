import copy
import itertools
import unittest
import numpy as np
from regime_lab import (P, SD, PRIOR, TRAIN, generate, infer, features, calibrate,
                        label_rows, evidence_asof, score)


class RegimeTests(unittest.TestCase):
    def test_generator_prefix(self):
        a, b = generate(50), generate(80)
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x, y[:50])

    def test_filter_prefix(self):
        _, x, _ = generate()
        full = infer(x)[1]
        for end in (1, 239, 311, 501):
            np.testing.assert_allclose(infer(x[:end])[1], full[:end], atol=1e-14)

    def test_future_perturbation(self):
        # Equal likelihood in both regimes makes the prefix deliberately ambiguous.
        ambiguous = SD[0] * np.sqrt(2*np.log(4)/(1-1/16))
        x = np.tile(ambiguous, (3, 1))
        x[2] = 0
        modified = x.copy()
        modified[2] = SD[1] * 3
        np.testing.assert_array_equal(infer(x)[1][:2], infer(modified)[1][:2])
        self.assertGreater(np.max(np.abs(infer(x)[2][:2]-infer(modified)[2][:2])), .1)

    def test_probabilities(self):
        _, x, _ = generate()
        for a in infer(x)[:3]:
            self.assertTrue(np.isfinite(a).all())
            self.assertTrue((a >= 0).all())
            np.testing.assert_allclose(a.sum(axis=1), 1, atol=1e-14)

    def test_missing_is_prediction(self):
        x = np.array([[.01]*4, [np.nan]*4])
        pred, filt, _, log_ev = infer(x)
        np.testing.assert_allclose(filt[1], pred[1])
        self.assertAlmostEqual(log_ev[1], 0)

    def test_partial_missing_marginal(self):
        x = np.array([[.01, np.nan, np.nan, np.nan]])
        a = infer(x)[1]
        b = infer(x[:, :1], scales=SD[:, :1])[1]
        np.testing.assert_allclose(a, b)

    def test_smoothing_exact_enumeration(self):
        x = np.array([[.001], [.02], [.003]])
        scales = SD[:, :1]
        expected = np.zeros((3, 2))
        total = 0.
        for path in itertools.product(range(2), repeat=3):
            w = PRIOR[path[0]]
            for t, state in enumerate(path):
                if t:
                    w *= P[path[t-1], state]
                sigma = scales[state, 0]
                w *= np.exp(-.5*(x[t, 0]/sigma)**2)/(np.sqrt(2*np.pi)*sigma)
            total += w
            for t, state in enumerate(path):
                expected[t, state] += w
        np.testing.assert_allclose(infer(x, scales=scales)[2], expected/total, atol=1e-13)

    def test_last_smoothing_equals_filter(self):
        _, x, _ = generate(40)
        _, f, s, _ = infer(x)
        np.testing.assert_array_equal(f[-1], s[-1])

    def test_rules_no_future(self):
        _, x, spreads = generate()
        all_rows = features(x, spreads)
        cfg = calibrate(all_rows)
        prefix = features(x[:400], spreads[:400])
        self.assertEqual(cfg, calibrate(prefix))
        self.assertEqual(label_rows(prefix, cfg), label_rows(all_rows, cfg)[:160])
        self.assertEqual(label_rows(all_rows, cfg)[0]["step"], TRAIN)

    def test_hysteresis_and_unknown(self):
        cfg = dict(available_step=-1, vol_enter=2, vol_exit=1, momentum_band=.02,
                   spread_high=5, version="test")
        seq = [1.9, 2.1, 1.8, None, 1.2, .9]
        rows = [dict(step=i, volatility=v, momentum=0, spread_bps=1)
                for i, v in enumerate(seq)]
        self.assertEqual([x["volatility"] for x in label_rows(rows, cfg)],
                         ["LOW", "HIGH", "HIGH", "UNKNOWN", "HIGH", "LOW"])

    def test_missing_window_no_imputation(self):
        _, x, spreads = generate()
        x[310] = np.nan
        rows = features(x, spreads)
        self.assertTrue(all(r["volatility"] is None for r in rows[310:330]))
        self.assertIsNotNone(rows[330]["volatility"])

    def test_evidence_versions(self):
        a = dict(id="a", reference_step=10, published_step=20, available_step=22,
                 version=1, label="A")
        b = dict(id="b", reference_step=10, published_step=30, available_step=32,
                 version=2, label="B")
        self.assertEqual(evidence_asof([b, a, a], 21), [])
        self.assertEqual(evidence_asof([b, a, a], 31), [a])
        self.assertEqual(evidence_asof([a, b], 32), [b])
        self.assertEqual(evidence_asof([a], 31), evidence_asof([a, b], 31))
        bad = copy.deepcopy(a)
        bad["label"] = "conflict"
        with self.assertRaises(ValueError):
            evidence_asof([a, bad], 40)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            infer([[np.inf]*4])
        with self.assertRaises(ValueError):
            infer([[0]*4], transition=[[.5, .6], [.1, .9]])
        with self.assertRaises(ValueError):
            calibrate(features(np.zeros((300, 4)), np.ones(300)))
        with self.assertRaises(ValueError):
            evidence_asof([dict(id="x", reference_step=10, published_step=9,
                                available_step=11, version=1)], 20)

    def test_score_and_zero_return_means(self):
        self.assertAlmostEqual(score([.8, .2], [1, 0])["brier"], .04)
        with self.assertRaises(ValueError):
            score([float("nan")], [1])
        # Every state has a symmetric, zero-mean return distribution.
        prior, filt, _, _ = infer([[0]*4])
        self.assertEqual(float((filt[0] @ P) @ np.zeros(2)), 0.)


if __name__ == "__main__":
    unittest.main()
