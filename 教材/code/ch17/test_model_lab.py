"""Contract, revision and transaction tests; all inputs are synthetic."""
import json
import sqlite3
import unittest
import model_lab as lab


class ModelLabTests(unittest.TestCase):
    def setUp(self):
        self.db = lab.connect(":memory:")
        lab.initialize(self.db)
        self.raw, self.received = lab.samples()[0]

    def tearDown(self):
        self.db.close()

    def put(self, obj=None, raw=None, received=None):
        if raw is None:
            raw = self.raw if obj is None else lab.dump(obj).encode("utf-8")
        return lab.ingest(self.db, "DEMO", raw, received or self.received)

    def obj(self, i=0):
        return json.loads(lab.samples()[i][0])

    def count(self, table):
        return self.db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]

    def test_exact_decimal_and_range(self):
        self.assertEqual(lab.atoms("100.100", 2), 10010)
        self.assertEqual(lab.atoms("-0.25", 2), -25)
        for value in ("100.101", "NaN", "1e2", str(2**63), 100.1):
            with self.subTest(value=value), self.assertRaises(lab.ContractError):
                lab.atoms(value, 2)

    def test_time_offset_precision_and_naive_rejection(self):
        self.assertEqual(lab.time_us("2026-10-28T09:00:00+08:00"),
                         lab.time_us("2026-10-28T01:00:00Z"))
        for value in ("2026-10-28T01:00:00", "2026-02-30T00:00:00Z",
                      "2026-10-28T01:00:00.0000001Z"):
            with self.subTest(value=value), self.assertRaises(lab.ContractError):
                lab.time_us(value)

    def test_semantic_duplicate_keeps_first_availability(self):
        self.assertEqual(self.put(), "ACCEPTED")
        obj = self.obj()
        obj["body"]["price"] = "100.100"
        self.assertEqual(self.put(obj, received="2026-10-28T01:00:05Z"), "DUPLICATE")
        self.assertEqual(self.count("event"), 1)
        hashes = [r[0] for r in self.db.execute("SELECT raw_sha256 FROM receipt")]
        self.assertEqual(len(set(hashes)), 2)
        self.assertEqual(self.db.execute("SELECT available_us FROM event").fetchone()[0],
                         lab.time_us(self.received))

    def test_same_key_conflict_does_not_overwrite(self):
        self.put()
        obj = self.obj(); obj["body"]["price"] = "100.11"
        self.assertEqual(self.put(obj), "QUARANTINED")
        self.assertEqual(self.db.execute("SELECT price_atoms FROM quote").fetchone()[0], 10010)
        self.assertEqual(self.db.execute("SELECT reason FROM receipt ORDER BY receipt_id DESC").fetchone()[0],
                         "SAME_KEY_CONFLICT")

    def test_revision_pit_and_late_older_version(self):
        rows = lab.samples()
        for i in (-1, 4):  # Version 2 arrives before a late delivery of version 1.
            raw, received = rows[i]
            if i == 4:
                received = "2026-10-28T02:10:00Z"
            lab.ingest(self.db, "DEMO", raw, received)
        self.assertEqual(lab.macro_asof(self.db, "2026-10-28T01:30:00Z"), [])
        self.assertEqual(lab.macro_asof(self.db, "2026-10-28T02:30:00Z")[0]["revision"], 2)

    def test_revision_cannot_leak_backwards(self):
        for raw, received in lab.samples():
            lab.ingest(self.db, "DEMO", raw, received)
        before = lab.macro_asof(self.db, "2026-10-28T01:30:00Z")
        after = lab.macro_asof(self.db, "2026-10-28T02:30:00Z")
        self.assertEqual((before[0]["value_atoms"], after[0]["value_atoms"]), (230, 210))
        self.assertEqual(lab.macro_asof(self.db, "2026-10-28T00:59:59Z"), [])

    def test_macro_business_key_is_stable(self):
        obj = self.obj(4); obj["event_key"] = "another-macro-key"
        self.assertEqual(self.put(obj), "QUARANTINED")
        self.assertEqual(self.count("macro"), 0)

    def test_alias_unknown_knowledge_and_half_open_interval(self):
        row = self.db.execute("SELECT * FROM alias WHERE external_code='EQ_DEMO'").fetchone()
        with self.assertRaises(lab.ContractError):
            lab.resolve(self.db, "DEMO", "UNKNOWN", row["valid_from_us"], row["known_at_us"])
        with self.assertRaises(lab.ContractError):
            lab.resolve(self.db, "DEMO", "EQ_DEMO", row["valid_to_us"], row["known_at_us"])
        with self.assertRaises(lab.ContractError):
            lab.resolve(self.db, "DEMO", "EQ_DEMO", row["valid_from_us"], row["known_at_us"]-1)

    def test_ambiguous_alias_is_quarantined(self):
        with self.db:
            self.db.execute("INSERT INTO alias VALUES (?,?,?,?,?,?)",
                            ("DEMO", "EQ_DEMO", lab.time_us("2021-01-01T00:00:00Z"),
                             lab.time_us("2030-01-01T00:00:00Z"), 0, "BOND_DEMO"))
        self.assertEqual(self.put(), "QUARANTINED")

    def test_unit_bool_quantity_and_future_publication(self):
        for field, value in (("unit", "USD/share"), ("quantity", True)):
            obj = self.obj(); obj["body"][field] = value
            self.assertEqual(self.put(obj), "QUARANTINED")
        obj = self.obj(); obj["published_at"] = "2026-10-28T01:00:02Z"
        self.assertEqual(self.put(obj), "QUARANTINED")
        self.assertEqual(self.count("event"), 0)
        self.assertEqual(self.count("receipt"), 3)

    def test_strict_json_and_unknown_schema(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"bad":', b'\xff'):
            self.assertEqual(self.put(raw=raw), "QUARANTINED")
        obj = self.obj(); obj["schema_version"] = 99
        self.assertEqual(self.put(obj), "QUARANTINED")
        obj = self.obj(); obj["extra"] = 1
        self.assertEqual(self.put(obj), "QUARANTINED")

    def test_version_two_default_preserves_semantics(self):
        self.put()
        obj = self.obj(); obj["schema_version"] = 2
        self.assertEqual(self.put(obj), "DUPLICATE")
        obj["body"]["quality"] = "FIRM"
        self.assertEqual(self.put(obj), "QUARANTINED")
        obj["event_key"] = "v2-new-key"
        self.assertEqual(self.put(obj), "ACCEPTED")

    def test_database_failure_keeps_pending_raw_and_rolls_back_event(self):
        self.db.execute("""CREATE TRIGGER fail_quote BEFORE INSERT ON quote
                           BEGIN SELECT RAISE(ABORT,'injected failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.put()
        self.assertEqual(self.count("event"), 0)
        self.assertEqual(self.count("quote"), 0)
        self.assertEqual(self.count("receipt"), 1)
        row = self.db.execute("SELECT raw,status FROM receipt").fetchone()
        self.assertEqual(tuple(row), (self.raw, "PENDING"))

    def test_foreign_key_is_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError), self.db:
            self.db.execute("INSERT INTO news_asset VALUES ('missing','EQ_DEMO')")
        self.assertEqual(list(self.db.execute("PRAGMA foreign_key_check")), [])

    def test_news_many_to_many_and_literal_text(self):
        obj = self.obj(5)
        obj["body"]["symbols"].append("EQ_DEMO")
        obj["body"]["headline"] = "'); DROP TABLE event; --"
        self.assertEqual(self.put(obj), "ACCEPTED")
        self.assertEqual(self.count("news_asset"), 2)
        self.assertEqual(self.db.execute("SELECT headline FROM news").fetchone()[0],
                         obj["body"]["headline"])
        self.assertEqual(self.count("event"), 1)

    def test_unknown_source_preserves_receipt(self):
        self.assertEqual(lab.ingest(self.db, "UNKNOWN", self.raw, self.received), "QUARANTINED")
        self.assertEqual(self.count("receipt"), 1)
        self.assertEqual(self.count("event"), 0)

    def test_complete_replay_is_idempotent_only_for_event_set(self):
        for repeat in range(2):
            for raw, received in lab.samples():
                lab.ingest(self.db, "DEMO", raw, received)
        self.assertEqual(self.count("event"), 8)
        self.assertEqual(self.count("receipt"), 24)
        counts = dict(self.db.execute("SELECT status,COUNT(*) FROM receipt GROUP BY status"))
        self.assertEqual(counts, {"ACCEPTED": 8, "DUPLICATE": 10, "QUARANTINED": 6})


if __name__ == "__main__":
    unittest.main()
