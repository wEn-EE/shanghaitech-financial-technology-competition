from dataclasses import replace
import sqlite3
import unittest
from pit_lab import (append, asof, current_at, freeze_feature, infer, new_db,
                     period_at, run, samples)


class PITTests(unittest.TestCase):
    def setUp(self):
        self.db = new_db()
        self.addCleanup(self.db.close)
        for row in samples():
            append(self.db, row)

    def test_ready_boundary(self):
        self.assertEqual(asof(self.db, 14), [])
        self.assertEqual(current_at(self.db, 15)["id"], "sep-v1")

    def test_received_is_not_ready(self):
        self.assertEqual(period_at(self.db, 70, "2026-09")["value"], 230)
        self.assertEqual(period_at(self.db, 80, "2026-09")["value"], 270)

    def test_filter_before_rank(self):
        self.assertEqual(period_at(self.db, 20, "2026-09")["id"], "sep-v1")
        wrong = self.db.execute("""
          SELECT id FROM vintage WHERE revision=(
            SELECT MAX(revision) FROM vintage WHERE period='2026-09'
          ) AND period='2026-09' AND ready<=20
        """).fetchall()
        self.assertEqual(wrong, [])

    def test_old_period_revision_does_not_replace_new_period(self):
        self.assertEqual(current_at(self.db, 90)["id"], "oct-v1")
        self.assertEqual(period_at(self.db, 90, "2026-09")["id"], "sep-v2")

    def test_withdrawal_not_resurrection(self):
        self.assertEqual(current_at(self.db, 109)["id"], "oct-v1")
        row = current_at(self.db, 110)
        self.assertEqual(row["id"], "oct-v2")
        self.assertIsNone(row["value"])
        feature = freeze_feature(self.db, 110, 111)
        rule = {"id": "r", "ready": 0, "threshold": 250}
        self.assertEqual(infer(feature, rule, 112)["label"], "UNKNOWN")

    def test_restoration(self):
        self.assertEqual(current_at(self.db, 129)["status"], "WITHDRAWN")
        self.assertEqual(current_at(self.db, 130)["value"], 260)

    def test_future_append_preserves_prefix(self):
        db = new_db()
        self.addCleanup(db.close)
        append(db, samples()[0])
        before = asof(db, 20)
        for v in samples()[1:]:
            append(db, replace(v, value=999) if v.status == "OK" else v)
        self.assertEqual(before, asof(db, 20))

    def test_physical_load_order_irrelevant(self):
        db = new_db()
        self.addCleanup(db.close)
        for row in reversed(samples()):
            append(db, row)
        for cut in (14, 15, 70, 80, 110, 130):
            self.assertEqual(asof(db, cut), asof(self.db, cut))

    def test_duplicate_and_conflict(self):
        self.assertEqual(append(self.db, samples()[0]), "DUPLICATE")
        with self.assertRaises(ValueError):
            append(self.db, replace(samples()[0], value=999))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM vintage").fetchone()[0], 5)

    def test_constraints_and_append_only(self):
        for v in (replace(samples()[0], period="2026-9"),
                  replace(samples()[0], revision=True),
                  replace(samples()[0], revision=4, id="bad", received=9)):
            with self.assertRaises((ValueError, sqlite3.IntegrityError)):
                append(self.db, v)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute("UPDATE vintage SET value=999 WHERE id='sep-v1'")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute("DELETE FROM vintage")
        self.assertEqual(current_at(self.db, 20)["value"], 230)

    def test_dependency_gate_and_snapshot(self):
        feature = freeze_feature(self.db, 70, 75)
        rule = {"id": "r2", "ready": 90, "threshold": 250}
        for cut in (74, 80, 89):
            with self.assertRaises(ValueError):
                infer(feature, rule, cut)
        prediction = infer(feature, rule, 90)
        self.assertEqual(prediction["label"], "LOW")
        self.assertEqual(prediction["feature"]["input"]["id"], "oct-v1")
        self.assertEqual(feature["input"]["value"], 240)
        with self.assertRaises(ValueError):
            freeze_feature(self.db, 70, 69)

    def test_end_to_end_and_replay(self):
        db = new_db()
        self.addCleanup(db.close)
        first = run(db)
        self.assertEqual(first, run(db))
        self.assertEqual(first["prediction_at_135"]["label"], "HIGH")
        self.assertEqual(first["wrong_rank_first_at_20"], [])
        self.assertEqual([r["pit"] for r in first["september_comparison"]],
                         [230, 230])
        self.assertEqual([r["restated"] for r in first["september_comparison"]],
                         [270, 270])


if __name__ == "__main__":
    unittest.main()
