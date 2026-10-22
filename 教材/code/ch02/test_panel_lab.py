"""金融时间与数据语义验证，不依赖外部下载。"""
import unittest
import numpy as np
import pandas as pd
from panel_lab import demo_data, prepare_quotes, build_panel, safe_returns, macro_asof


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.assets, self.macro, self.clock = demo_data()
        self.cutoff = "2025-01-06T01:34:00Z"

    def panel(self, cutoff=None):
        cutoff = cutoff or self.cutoff
        quotes, audit = prepare_quotes(self.raw, self.assets, cutoff)
        return build_panel(quotes, self.assets, self.clock, cutoff), audit

    def test_accounting_and_original_unchanged(self):
        saved = self.raw.copy(deep=True)
        frames, audit = self.panel()
        pd.testing.assert_frame_equal(self.raw, saved)
        self.assertEqual(audit["status"].value_counts().to_dict(), {"accepted": 15, "not_available": 1})
        self.assertEqual(frames["returns"].shape, (4, 4))
        self.assertEqual(frames["returns"].count().tolist(), [3, 3, 1, 3])

    def test_numpy_equals_pandas_and_scalar_reference(self):
        frames, _ = self.panel()
        returns = frames["returns"]
        reference = frames["prices"].pct_change(fill_method=None)
        pd.testing.assert_frame_equal(returns, reference, check_names=False)
        eq = returns["EQ_DEMO"].dropna().to_numpy()
        np.testing.assert_allclose(eq, [(101-100)/100, (99.99-101)/101, (102-99.99)/99.99],
                                   rtol=1e-12, atol=1e-15)
        self.assertAlmostEqual(frames["summary"].loc["EQ_DEMO", "sample_std"], 0.015319821736581673)

    def test_missing_does_not_become_zero_or_bridge(self):
        frames, _ = self.panel()
        gold = frames["returns"]["GOLD_DEMO"]
        self.assertTrue(np.isnan(gold.iloc[2]))
        self.assertTrue(np.isnan(gold.iloc[3]))
        self.assertAlmostEqual(gold.iloc[1], 0.01)

    def test_coverage_and_no_implicit_reweighting(self):
        frames, _ = self.panel()
        monitor = frames["monitoring"]
        np.testing.assert_allclose(monitor["coverage"], [0, 1, 0.8, 0.8])
        self.assertAlmostEqual(monitor["weighted_monitor_score"].iloc[1], 0.0067)
        self.assertTrue(monitor["weighted_monitor_score"].iloc[[0, 2, 3]].isna().all())

    def test_future_arrival_does_not_rewrite_past_decisions(self):
        early, _ = self.panel()
        later, audit = self.panel("2025-01-06T01:35:00Z")
        self.assertEqual(audit["status"].value_counts().to_dict(), {"accepted": 16})
        for name in ("prices", "returns", "monitoring", "rolling_std"):
            pd.testing.assert_frame_equal(early[name], later[name])

    def test_previous_endpoint_may_arrive_after_previous_decision(self):
        quotes, _ = prepare_quotes(self.raw, self.assets, self.cutoff)
        quotes.loc[quotes["event_id"].eq("EQ_DEMO-0"), "available_time"] = pd.Timestamp(
            "2025-01-06T01:30:20Z")
        frames = build_panel(quotes, self.assets, self.clock, self.cutoff)
        self.assertTrue(np.isnan(frames["prices"]["EQ_DEMO"].iloc[0]))
        self.assertAlmostEqual(frames["returns"]["EQ_DEMO"].iloc[1], 0.01)

    def test_macro_release_revision_and_query_order(self):
        result = macro_asof(["2025-01-06T01:33:25Z", "2025-01-06T01:31:01Z",
                             "2025-01-06T01:31:03Z", "2025-01-06T01:33:10Z"],
                            self.macro, self.cutoff)
        self.assertAlmostEqual(result["value"].iloc[0], 2.1)
        self.assertTrue(np.isnan(result["value"].iloc[1]))
        np.testing.assert_allclose(result["value"].iloc[2:], [1.9, 1.9])
        self.assertTrue((result["age"].dropna() >= pd.Timedelta(0)).all())

    def test_safe_division_and_shape_contract(self):
        with np.errstate(all="raise"):
            result = safe_returns([2, 2, 2, np.nan], [1, 0, np.nan, 1])
        self.assertEqual(result[0], 1)
        self.assertTrue(np.isnan(result[1:]).all())
        with self.assertRaises(ValueError):
            safe_returns([[1, 2]], [1, 2])
        with self.assertRaises(FloatingPointError):
            safe_returns([1e308], [1e-308])

    def test_quality_flags_preserve_invalid_rows(self):
        for value in (True, "oops", 0, np.inf):
            with self.subTest(value=repr(value)):
                raw = self.raw.copy(deep=True)
                raw["price"] = raw["price"].astype("object")
                raw.loc[0, "price"] = value
                _, audit = prepare_quotes(raw, self.assets, self.cutoff)
                self.assertEqual(len(audit), len(raw))
                self.assertEqual(audit.loc[0, "status"], "invalid_price")
        raw = self.raw.copy(deep=True)
        raw.loc[0, "event_time"] = "2025-01-06T01:30:00"
        _, audit = prepare_quotes(raw, self.assets, self.cutoff)
        self.assertEqual(audit.loc[0, "status"], "invalid_time")

    def test_duplicate_metadata_and_messages_fail_explicitly(self):
        with self.assertRaises(ValueError):
            prepare_quotes(self.raw, pd.concat([self.assets, self.assets.iloc[[0]]]), self.cutoff)
        with self.assertRaises(ValueError):
            prepare_quotes(pd.concat([self.raw, self.raw.iloc[[0]]], ignore_index=True),
                           self.assets, self.cutoff)

    def test_empty_cutoff_and_macro_query_contract(self):
        frames, _ = self.panel("2025-01-06T01:30:00Z")
        self.assertEqual(frames["returns"].shape, (0, 4))
        for queries in (["2025-01-06T01:31:01"], ["2025-01-07T01:31:01Z"]):
            with self.assertRaises(ValueError):
                macro_asof(queries, self.macro, self.cutoff)
        broken = self.macro.copy()
        broken["revision"] = [1, 0]
        with self.assertRaises(ValueError):
            macro_asof(["2025-01-06T01:33:25Z"], broken, self.cutoff)


if __name__ == "__main__":
    unittest.main()
