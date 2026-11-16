import copy
from pathlib import Path
import sys
import unittest

import numpy as np

from nested_lab import eligible, evaluate, fit, outer_fold, predict, prepare, period

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ch23"))
from fusion_lab import build, fixture


class NestedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build(*fixture())
        cls.rows = prepare(cls.payload)
        cls.report = evaluate(cls.payload)

    def test_timing_and_common_rows(self):
        index = {tuple(row["key"]): row for row in self.rows}
        for fold in self.report["folds"]:
            start = fold["start"]
            self.assertEqual(len(fold["test_keys"]), 64)
            for key in fold["training_keys"]:
                self.assertLess(index[tuple(key)]["ready"], start)
            groups = fold["groups"]
            self.assertEqual(groups["market"]["inner"], groups["market_news"]["inner"])
            for group in groups.values():
                self.assertEqual(len(group["trials"]), 6)
                self.assertEqual(len(group["prediction"]), 64)
                for inner in group["inner"]:
                    self.assertLess(inner["last_label_ready"], start)
                    for key in inner["training_keys"]:
                        self.assertLess(index[tuple(key)]["ready"], inner["start"])
                self.assertAlmostEqual(group["mse"], float(np.mean(
                    (np.array(group["prediction"]) - fold["actual"]) ** 2)))
        self.assertEqual(len({tuple(key) for f in self.report["folds"]
                              for key in f["test_keys"]}), 192)

    def test_unmatured_label_perturbation(self):
        rows = copy.deepcopy(self.rows)
        original = outer_fold(rows, 48)
        for row in rows:
            if row["ready"] >= 48:
                row["y"] += 1
        changed = outer_fold(rows, 48)
        for name in original["groups"]:
            for key in ("model", "choice", "trials", "prediction"):
                self.assertEqual(original["groups"][name][key], changed["groups"][name][key])
        self.assertNotEqual(original["zero_mse"], changed["zero_mse"])

    def test_missing_and_constant_hand_example(self):
        rows = [{"x": {"return_last": x, "news_score": None}, "y": y}
                for x, y in [(-1, -2), (1, 2), (None, 0)]]
        model = fit(rows, ("return_last", "news_score"), 2, 1.0)
        self.assertEqual(model["fill"], [0, 0])
        self.assertEqual(model["selected"], [0])
        np.testing.assert_allclose(predict(model, rows), [-1, 1, 0])

    def test_no_eligible_label_at_exact_cutoff(self):
        self.assertEqual(eligible([{"t": 45, "ready": 48}], 48), [])

    def test_reject_invalid_input(self):
        for corrupt in ("duplicate", "late", "missing_label", "wrong_model"):
            payload = copy.deepcopy(self.payload)
            if corrupt == "duplicate":
                payload["labels"].append(payload["labels"][0])
            elif corrupt == "late":
                payload["features"][0]["feature_ready"] += 1
            elif corrupt == "wrong_model":
                payload["features"][0]["model_id"] = "unrelated"
            else:
                payload["labels"].pop()
            with self.subTest(corrupt=corrupt), self.assertRaises(ValueError):
                prepare(payload)

    def test_missing_panel_row(self):
        rows = [row for row in self.rows if row["key"] != ["EQ_DEMO", 48]]
        with self.assertRaises(ValueError):
            period(rows, 48, 16)


if __name__ == "__main__":
    unittest.main()
