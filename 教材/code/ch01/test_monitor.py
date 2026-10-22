"""验证金融数据语义，而不仅是语法是否能执行。"""
import json
import math
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from monitor import Monitor, demo_lines, parse_quote, run


class MonitorTests(unittest.TestCase):
    def test_demo_accounting_and_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run"
            result = run(demo_lines(), target)
            self.assertEqual(result["counts"], {
                "accepted": 10, "duplicate": 1, "late": 1,
                "invalid": 2, "conflict": 1})
            equity = next(x for x in result["latest"] if x["symbol"] == "EQ_DEMO")
            self.assertAlmostEqual(equity["return"], 102 / 99.99 - 1)
            self.assertAlmostEqual(equity["mean"], (0.01 - 0.01 + 102 / 99.99 - 1) / 3)
            self.assertTrue(equity["jump_alert"])
            self.assertFalse(equity["warmup"])
            records = [json.loads(s) for s in (target / "audit.jsonl").read_text(
                encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 15)
            self.assertEqual(records[-1]["raw"], "{broken json")
            self.assertIsNone(records[0]["feature"]["return"])

    def test_bad_numeric_and_timestamp(self):
        row = json.loads(demo_lines()[0])
        for bad in (True, 0, -1, "100", float("nan"), float("inf")):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                parse_quote(json.dumps({**row, "price": bad}))
        with self.assertRaises(ValueError):
            parse_quote(json.dumps({**row, "event_time": "2025-01-06T01:30:00"}))
        with self.assertRaises(ValueError):
            parse_quote(json.dumps({**row, "published_time": "2025-01-07T01:30:00Z"}))

    def test_duplicate_conflict_and_late_do_not_change_latest(self):
        engine = Monitor()
        first = parse_quote(demo_lines()[0])
        engine.process(first)
        replay = replace(first, available_time=first.available_time + timedelta(seconds=1))
        self.assertEqual(engine.process(replay)[0], "duplicate")
        self.assertEqual(engine.process(replace(replay, price=999))[0], "conflict")
        late = replace(replay, event_id="late", event_time=first.event_time - timedelta(seconds=1))
        self.assertEqual(engine.process(late)[0], "late")
        self.assertEqual(engine.latest[(first.source, first.symbol)].price, 100)

    def test_window_matches_independent_two_pass_statistics(self):
        engine = Monitor(window=3)
        first = parse_quote(demo_lines()[0])
        expected = []
        previous_price = None
        for i, price in enumerate([100, 110, 99, 105, 90, 95]):
            q = replace(first, event_id=str(i), price=price,
                        event_time=first.event_time + timedelta(seconds=i),
                        published_time=first.published_time + timedelta(seconds=i),
                        available_time=first.available_time + timedelta(seconds=i))
            feature = engine.process(q)[2]
            if previous_price is not None:
                expected.append((price - previous_price) / previous_price)
            previous_price = price
            values = expected[-3:]
            if len(values) >= 2:
                mean = sum(values) / len(values)
                std = math.sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))
                self.assertAlmostEqual(feature["sample_std"], std)
        self.assertEqual(feature["count"], 3)

    def test_future_suffix_does_not_change_past_feature(self):
        rows = [parse_quote(s) for s in demo_lines()[:10]]
        short, long = Monitor(), Monitor()
        prefix = [short.process(q) for q in rows[:5]]
        complete = [long.process(q) for q in rows]
        self.assertEqual(prefix, complete[:5])

    def test_out_of_receipt_order_is_explicit(self):
        engine = Monitor()
        later = parse_quote(demo_lines()[4])
        earlier = parse_quote(demo_lines()[0])
        engine.process(later)
        self.assertEqual(engine.process(earlier)[0], "invalid")


if __name__ == "__main__":
    unittest.main()
