import copy
import math
import unittest
from derivatives_lab import (bs_call, crr_call, fx_forward, implied_vol, inverse_quote,
                             forward_value, margin_stress, one_step, price_change,
                             roll_ledger, synthetic_inputs)


class DerivativesTests(unittest.TestCase):
    def ledger(self, data=None, **kwargs):
        data = synthetic_inputs() if data is None else data
        return roll_ledger(data["rows"], data["schedule"], **kwargs)

    def test_roll_uses_held_contract(self):
        ledger = self.ledger()
        self.assertEqual([r["variation"] for r in ledger], [0, 10, 10, 10])
        self.assertEqual([r["equity"] for r in ledger], [1000, 1006, 1016, 1026])
        self.assertEqual(ledger[1]["earned_on"], "GOLD_DEMO_NEAR")

    def test_no_roll_and_fee_identity(self):
        data = synthetic_inputs()
        data["schedule"] = ["GOLD_DEMO_NEAR"] * 4
        self.assertEqual(self.ledger(data)[-1]["equity"], 1030)
        for fee in (0, 2, 10):
            ledger = self.ledger(fee_per_leg=fee)
            self.assertEqual(ledger[-1]["equity"], 1030 - 2 * fee)

    def test_missing_contract_rejected(self):
        data = synthetic_inputs()
        del data["rows"][1]["prices"]["GOLD_DEMO_NEAR"]
        with self.assertRaises(ValueError):
            self.ledger(data)

    def test_time_safety(self):
        for key, value in [("available_at", 2), ("event_at", 0)]:
            data = copy.deepcopy(synthetic_inputs())
            data["rows"][1][key] = value
            with self.assertRaises(ValueError):
                self.ledger(data)
        with self.assertRaises(ValueError):
            self.ledger(schedule_available=.2)

    def test_quote_inversion(self):
        inverse = inverse_quote(7.19, 7.21)
        self.assertLess(inverse[0], inverse[1])
        for a, b in zip(inverse_quote(*inverse), (7.19, 7.21)):
            self.assertAlmostEqual(a, b)

    def test_cip_hedged_wealth(self):
        f = fx_forward(7.2, .02, .05, 1)
        self.assertAlmostEqual(math.exp(.05) * f / 7.2, math.exp(.02))
        self.assertAlmostEqual(f * fx_forward(1 / 7.2, .05, .02, 1), 1)

    def test_forward_values(self):
        self.assertEqual(forward_value(7, 7, .02, 1), 0)
        self.assertEqual(forward_value(8, 7, .02, 0, 100), 100)

    def test_negative_price_is_not_deleted(self):
        result = price_change(20, -5)
        self.assertEqual(result["difference"], -25)
        self.assertIsNone(result["log_return"])
        self.assertEqual(price_change(-5, -2)["difference"], 3)
        self.assertIsNone(price_change(-5, -2)["log_return"])

    def test_margin_not_maximum_loss(self):
        self.assertEqual(margin_stress(100, 100, 88, 10, 80),
                         {"equity_after": -20, "cash_shortfall": 100})

    def test_replication_both_states(self):
        result = one_step(100, 100, 1.2, .8, 1.05)
        for factor, payoff in [(1.2, 20), (.8, 0)]:
            self.assertAlmostEqual(result["delta"] * 100 * factor +
                                   result["cash"] * 1.05, payoff)
        self.assertAlmostEqual(result["call"], 20 * .625 / 1.05)

    def test_crr_against_replication(self):
        u = math.exp(.2)
        reference = one_step(100, 100, u, 1 / u, math.exp(.05))["call"]
        self.assertAlmostEqual(crr_call(100, 100, .05, .2, 1, 1), reference)

    def test_crr_converges_to_independent_bs_formula(self):
        expected = bs_call(100, 100, .05, .2, 1)
        self.assertAlmostEqual(expected, 10.450583572185565)
        for n in [400, 401]:
            self.assertLess(abs(crr_call(100, 100, .05, .2, 1, n) - expected), .006)

    def test_iv_and_greek_finite_difference(self):
        for sigma in (.1, .2, .7):
            value = bs_call(100, 100, .05, sigma, 1)
            self.assertAlmostEqual(implied_vol(value, 100, 100, .05, 1), sigma, places=8)
        h = 1e-3
        delta = (bs_call(100+h, 100, .05, .2, 1)-bs_call(100-h, 100, .05, .2, 1))/(2*h)
        self.assertAlmostEqual(delta, .6368306511756191, places=7)

    def test_explicit_failure_boundaries(self):
        for spot in (0, -5, float("nan"), True):
            with self.assertRaises(ValueError):
                bs_call(spot, 100, .05, .2, 1)
        for price in (-1, 100, 101):
            with self.assertRaises(ValueError):
                implied_vol(price, 100, 100, .05, 1)
        with self.assertRaises(ValueError):
            implied_vol(bs_call(100, 100, .05, .7, 1), 100, 100, .05, 1, high=.3)
        with self.assertRaises(ValueError):
            crr_call(100, 100, 1, .01, 1, 1)
        with self.assertRaises(ValueError):
            bs_call(100, 100, .05, .2, 0)


if __name__ == "__main__":
    unittest.main()
