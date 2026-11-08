import copy
import math
from statistics import fmean, stdev
import unittest
from features_lab import (ALPHA, ASSETS, Engine, NAMES, fit, macro_at, macro_inputs,
                          panel, quantile, run, samples, transform)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.bars = samples()
        self.raw = panel(self.bars)
        self.train = [r for r in self.raw if r["ready"] <= 40]
        self.scaler = fit(self.train)

    def row(self, t, a="EQ_DEMO"):
        return next(r for r in self.raw if r["t"] == t and r["asset"] == a)

    def test_independent_batch_reference(self):
        for a in ASSETS:
            history, contiguous = [], []
            for b in [b for b in self.bars if b["asset"] == a]:
                history.append(b)
                contiguous = [] if b["price"] is None else contiguous + [b["price"]]
                x = self.row(b["t"], a)["x"]
                if contiguous:
                    n = len(contiguous)
                    ema = (1 - ALPHA) ** (n - 1) * contiguous[0]
                    ema += sum(ALPHA * (1 - ALPHA) ** (n - 1 - i) * contiguous[i]
                               for i in range(1, n))
                    self.assertAlmostEqual(x["ema_gap"], b["price"] / ema - 1, places=12)
                else:
                    self.assertIsNone(x["ema_gap"])
                w = history[-6:]
                if len(w) == 6 and all(v["price"] is not None for v in w):
                    returns = [w[i]["price"] / w[i - 1]["price"] - 1 for i in range(1, 6)]
                    self.assertAlmostEqual(x["mom5"], math.prod(1 + r for r in returns) - 1)
                    self.assertAlmostEqual(x["vol5"], stdev(returns))
                    if all(v["notional"] > 0 for v in w[1:]):
                        ref = sum(abs(r) / v["notional"]
                                  for r, v in zip(returns, w[1:])) / 5
                        self.assertAlmostEqual(x["impact5"], ref, places=18)
                    else:
                        self.assertIsNone(x["impact5"])
                else:
                    self.assertIsNone(x["mom5"])
                    self.assertIsNone(x["vol5"])

    def test_warmup(self):
        self.assertIsNone(self.row(4)["x"]["vol5"])
        self.assertIsNotNone(self.row(5)["x"]["vol5"])
        self.assertEqual(self.scaler["params"]["EQ_DEMO"]["mom5"]["n"], 35)

    def test_gap_not_bridge(self):
        for t in range(55, 61):
            self.assertIsNone(self.row(t)["x"]["mom5"])
        self.assertIsNone(self.row(56)["x"]["ret1"])
        self.assertEqual(self.row(56)["x"]["ema_gap"], 0)
        self.assertEqual(self.row(56)["ema_start_id"], "EQ_DEMO-56")
        self.assertIsNotNone(self.row(61)["x"]["vol5"])

    def test_zero_volume_does_not_zero_risk(self):
        for t in range(60, 65):
            x = self.row(t, "FX_DEMO")["x"]
            self.assertIsNone(x["impact5"])
            self.assertIsNotNone(x["vol5"])
        self.assertIsNotNone(self.row(65, "FX_DEMO")["x"]["impact5"])

    def test_train_standardization(self):
        for a in ASSETS:
            for k in NAMES:
                p = self.scaler["params"][a][k]
                vals = [(r["x"][k] - p["center"]) / p["scale"] for r in self.train
                        if r["asset"] == a and all(v is not None for v in r["x"].values())]
                self.assertAlmostEqual(fmean(vals), 0, places=12)
                self.assertAlmostEqual(fmean(v * v for v in vals), 1, places=12)

    def test_constant_and_quantiles(self):
        rows = copy.deepcopy(self.train)
        for r in rows:
            r["x"] = dict.fromkeys(NAMES, 2.0)
        model = fit(rows)
        self.assertTrue(model["params"]["EQ_DEMO"]["ret1"]["constant"])
        self.assertEqual(model["params"]["EQ_DEMO"]["ret1"]["scale"], 1)
        self.assertEqual(quantile([0, 10, 20, 30], 0.25), 7.5)
        robust = fit(self.train, "robust")
        self.assertEqual(robust["kind"], "robust")

    def test_future_training_and_early_transform_rejected(self):
        with self.assertRaises(ValueError):
            fit(self.raw)
        with self.assertRaises(ValueError):
            transform(self.row(39), self.scaler)

    def test_future_mutation(self):
        changed = copy.deepcopy(self.bars)
        for b in changed:
            if b["t"] >= 72 and b["price"] is not None:
                for k in ("price", "bid", "ask"):
                    b[k] *= 9
        other = panel(changed)
        self.assertEqual(fit([r for r in other if r["ready"] <= 40]), self.scaler)
        self.assertEqual([r for r in other if r["t"] < 72],
                         [r for r in self.raw if r["t"] < 72])

    def test_prefix_replay(self):
        short = panel(samples(50))
        self.assertEqual(short, [r for r in self.raw if r["t"] < 50])

    def test_clip_preserves_shock(self):
        r = transform(self.row(72), self.scaler)
        self.assertAlmostEqual(r["x"]["ret1"], -0.08)
        self.assertLess(r["z"]["ret1"], -4)
        self.assertEqual(r["clipped_z"]["ret1"], -4)
        self.assertTrue(r["clipped"]["ret1"])

    def test_order_and_invalid_input(self):
        e = Engine()
        with self.assertRaises(ValueError):
            e.step(self.bars[4])
        bad = dict(self.bars[0], price=-1)
        with self.assertRaises(ValueError):
            e.step(bad)

    def test_price_scale_invariance(self):
        changed = copy.deepcopy(self.bars)
        for b in changed:
            if b["price"] is not None:
                for k in ("price", "bid", "ask"):
                    b[k] *= 100
        for r, s in zip(self.raw, panel(changed)):
            for k in NAMES:
                if r["x"][k] is None:
                    self.assertIsNone(s["x"][k])
                else:
                    self.assertAlmostEqual(r["x"][k], s["x"][k], places=10)

    def test_macro_first_revision_and_forecast_boundary(self):
        releases, forecasts = macro_inputs()
        self.assertIsNone(macro_at(45, releases, forecasts))
        first = macro_at(46, releases, forecasts)
        self.assertAlmostEqual(first["surprise_pp"], 0.2)
        self.assertEqual(first["forecast_id"], "sep-pre")
        later = macro_at(66, releases, forecasts)
        self.assertEqual(later["level"], 2.7)
        self.assertAlmostEqual(later["revision_pp"], 0.4)
        self.assertAlmostEqual(later["surprise_pp"], 0.2)
        self.assertAlmostEqual(macro_at(56, releases, forecasts)["decayed_surprise"], 0.1)
        self.assertAlmostEqual(macro_at(81, releases, forecasts)["surprise_pp"], -0.1)

    def test_macro_prefix_and_missing_forecast(self):
        releases, forecasts = macro_inputs()
        early = macro_at(46, releases, forecasts)
        releases[1]["value"] = 999
        self.assertEqual(early, macro_at(46, releases, forecasts))
        self.assertIsNone(macro_at(46, releases, [])["surprise_pp"])
        self.assertEqual(len(run()["online"]), 224)


if __name__ == "__main__":
    unittest.main()
