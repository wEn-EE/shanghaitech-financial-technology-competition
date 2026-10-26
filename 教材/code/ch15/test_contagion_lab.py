import copy
import unittest

import numpy as np

from contagion_lab import configuration, dependence, linear_network, stress, tail_rate


class ContagionTests(unittest.TestCase):
    def test_no_shock_no_trade(self):
        cfg = configuration()
        cfg["external_drop"] = [0, 0, 0, 0]
        out = stress(cfg, .15)
        self.assertEqual(out["rounds"], 0)
        np.testing.assert_allclose(out["total_loss"], 0)

    def test_zero_impact_exact_target_and_loss(self):
        out = stress(configuration(), 0)
        self.assertEqual(out["rounds"], 1)
        np.testing.assert_allclose(out["total_loss"], [4, .8, 0], atol=1e-12)
        np.testing.assert_allclose(out["final_debt"], [64, 76.8, 80], atol=1e-12)

    def test_cashflows_and_inventory_conservation(self):
        cfg = configuration()
        out = stress(cfg, .15)
        sold = sum(np.array(t["sold_units"]) for t in out["trace"])
        proceeds = sum(np.array(t["proceeds"]) for t in out["trace"])
        np.testing.assert_allclose(np.array(cfg["holdings_units"]) - sold, out["final_holdings"])
        np.testing.assert_allclose(np.array(cfg["debt"]) - proceeds, out["final_debt"])
        self.assertTrue(np.all(np.array(out["final_holdings"]) >= 0))
        self.assertTrue(np.all(np.array(out["final_debt"]) >= 0))

    def test_equity_loss_telescopes_without_double_counting(self):
        out = stress(configuration(), .15)
        mark = sum(np.array(t["mark_loss"]) for t in out["trace"])
        np.testing.assert_allclose(mark, out["endogenous_loss"], atol=1e-12)
        self.assertLess(max(t["accounting_error_max"] for t in out["trace"]), 1e-12)

    def test_zero_direct_exposure_still_loses(self):
        out = stress(configuration(), .15)
        self.assertEqual(out["direct_loss"][2], 0)
        self.assertGreater(out["endogenous_loss"][2], 1)
        self.assertTrue(np.all(np.array(out["leverage_excess_value"]) <= 1e-9))

    def test_institution_order_invariance(self):
        cfg = configuration()
        original = stress(cfg, .15)
        order = [2, 0, 1]
        cfg["holdings_units"] = [cfg["holdings_units"][i] for i in order]
        cfg["debt"] = [cfg["debt"][i] for i in order]
        shuffled = stress(cfg, .15)
        np.testing.assert_allclose(shuffled["total_loss"], np.array(original["total_loss"])[order])
        np.testing.assert_allclose(shuffled["final_prices"], original["final_prices"])

    def test_max_rounds_is_not_success(self):
        out = stress(configuration(), .15, max_rounds=1)
        self.assertEqual(out["status"], "MAX_ROUNDS")
        self.assertGreater(max(out["leverage_excess_value"]), 1e-9)

    def test_insolvency_stops_without_fake_clearing(self):
        cfg = configuration()
        cfg["external_drop"] = [.9, 0, 0, 0]
        out = stress(cfg, .15)
        self.assertEqual(out["status"], "INSOLVENT_STOP")
        self.assertLess(out["final_equity"][0], 0)
        self.assertEqual(out["rounds"], 0)

    def test_input_immutable(self):
        cfg = configuration()
        original = copy.deepcopy(cfg)
        stress(cfg, .15)
        self.assertEqual(cfg, original)

    def test_pit_and_invalid_inputs(self):
        for key, value in (("available_at", "2026-10-28T00:00:00+00:00"),
                           ("depth_units", [0, 100, 100, 100]),
                           ("debt", [80, float("nan"), 80]),
                           ("initial_prices", [1, 1])):
            cfg = configuration()
            cfg[key] = value
            with self.assertRaises(ValueError):
                stress(cfg, .15)

    def test_network_orientation_and_closed_form(self):
        out = linear_network([[0, .2], [.1, 0]], [1, 0])
        np.testing.assert_allclose(out["total"], [1/.98, .1/.98], atol=1e-11)
        self.assertLess(out["solve_error"], 1e-11)

    def test_network_instability_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNSTABLE"):
            linear_network([[0, 2], [1, 0]], [1, 0])

    def test_dependence_population_examples(self):
        stats, _ = dependence()
        self.assertAlmostEqual(stats["calm_correlation"], .6/np.sqrt(1.36), delta=.01)
        self.assertAlmostEqual(stats["volatile_correlation"], 1.8/np.sqrt(4.24), delta=.01)
        for name in ("gaussian", "mixture"):
            self.assertAlmostEqual(stats[name]["correlation"], .4, delta=.01)
        self.assertAlmostEqual(stats["mixture"]["tails"][1]["conditional_rate"], .406, delta=.06)
        self.assertLess(stats["gaussian"]["tails"][1]["conditional_rate"], .2)

    def test_empty_tail_condition_is_missing(self):
        result = tail_rate(np.ones(5), np.ones(5), .01)
        self.assertEqual(result["conditioning_count"], 0)
        self.assertIsNone(result["conditional_rate"])


if __name__ == "__main__":
    unittest.main()
