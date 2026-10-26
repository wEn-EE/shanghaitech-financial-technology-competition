import unittest
from dataclasses import replace
from datetime import timedelta

from macro_lab import Ledger, dataset, experiment, forecast_before, surprise


class MacroTests(unittest.TestCase):
    def setUp(self):
        self.events, self.forecasts, self.decisions = dataset()
        self.e = next(e for e in self.events if e.series == "GROWTH_DEMO" and e.version == 1)
        self.ledger = Ledger()
        for e in self.events:
            self.ledger.add(e)

    def test_before_publication_and_acquisition(self):
        self.assertIsNone(self.ledger.snapshot(self.e.series, self.e.published_at)[0])
        self.assertEqual(self.ledger.snapshot(self.e.series, self.e.available_at)[0], self.e)

    def test_delayed_release_uses_previous_period(self):
        e, status = self.ledger.snapshot("GROWTH_DEMO", self.decisions[10])
        self.assertEqual(e.event_id, "GROWTH_DEMO:09:1")
        self.assertEqual(status, "OK")

    def test_old_revision_cannot_replace_new_period(self):
        revision = next(e for e in self.events if e.event_id == "GROWTH_DEMO:00:2")
        selected, _ = self.ledger.snapshot(revision.series, revision.available_at)
        self.assertGreater(selected.period_end, revision.period_end)

    def test_late_first_cannot_roll_back_revision(self):
        l = Ledger()
        rev = replace(self.e, event_id="R", version=2,
                      published_at=self.e.published_at + timedelta(days=1),
                      available_at=self.e.published_at + timedelta(days=1))
        late = replace(self.e, available_at=rev.available_at + timedelta(days=1))
        l.add(rev)
        l.add(late)
        self.assertEqual(l.snapshot(self.e.series, late.available_at)[0], rev)

    def test_duplicate_conflict_and_version_order(self):
        self.assertFalse(self.ledger.add(self.e))
        with self.assertRaisesRegex(ValueError, "ID_CONFLICT"):
            self.ledger.add(replace(self.e, value=self.e.value + 1))
        with self.assertRaisesRegex(ValueError, "VERSION_CONFLICT"):
            self.ledger.add(replace(self.e, event_id="OTHER"))
        with self.assertRaisesRegex(ValueError, "VERSION_ORDER"):
            self.ledger.add(replace(self.e, event_id="EARLY", version=3))

    def test_invalid_data_logged_and_not_inserted(self):
        bad = replace(self.e, event_id="BAD", value=float("nan"))
        with self.assertRaises(ValueError):
            self.ledger.add(bad)
        self.assertNotIn("BAD", self.ledger.events)
        self.assertEqual(self.ledger.audit[-1]["action"], "VALUE_OR_VERSION")

    def test_naive_and_inverted_time(self):
        for changed in (replace(self.e, period_end=self.e.period_end.replace(tzinfo=None)),
                        replace(self.e, available_at=self.e.published_at - timedelta(seconds=1))):
            with self.assertRaises(ValueError):
                Ledger().add(changed)

    def test_post_release_forecast_and_exact_boundary_excluded(self):
        e = next(e for e in self.events if e.event_id == "INFLATION_DEMO:12:1")
        self.assertIsNone(forecast_before(e, self.forecasts))
        f = replace(self.forecasts[0], series=e.series, period_end=e.period_end,
                    available_at=e.published_at)
        self.assertIsNone(forecast_before(e, [f]))

    def test_surprise_future_and_revision_invariance(self):
        e = next(e for e in self.events if e.event_id == "GROWTH_DEMO:20:1")
        past = Ledger()
        for row in self.events:
            if row.available_at <= e.available_at and row.version == 1:
                past.add(row)
        self.assertEqual(surprise(e, past, self.forecasts),
                         surprise(e, self.ledger, self.forecasts))
        self.assertEqual(surprise(e, past, self.forecasts)["history_n"], 20)

    def test_revision_cannot_be_first_surprise(self):
        revision = next(e for e in self.events if e.version == 2)
        with self.assertRaises(ValueError):
            surprise(revision, self.ledger, self.forecasts)

    def test_staleness_keeps_evidence(self):
        t = max(e.available_at for e in self.events) + timedelta(days=100)
        e, status = self.ledger.snapshot("GROWTH_DEMO", t)
        self.assertIsNotNone(e)
        self.assertEqual(status, "STALE")

    def test_replay_matches_full_store_asof(self):
        for t in self.decisions:
            prefix = Ledger()
            for e in self.events:
                if e.available_at <= t:
                    prefix.add(e)
            for s in ("GROWTH_DEMO", "INFLATION_DEMO"):
                self.assertEqual(prefix.snapshot(s, t), self.ledger.snapshot(s, t))
        result, _, surprises, _, _ = experiment(self.events, self.forecasts, self.decisions)
        self.assertEqual(result["missing_pre_release_forecasts"], 1)
        self.assertTrue(any(s["z"] is not None for s in surprises))


if __name__ == "__main__":
    unittest.main()
