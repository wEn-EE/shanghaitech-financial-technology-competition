import sqlite3
import tempfile
import unittest
from pathlib import Path

from storage_lab import DAY, LATEST, archive, cold_window, compare, equity_feature, load


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        load(self.db, [("EQ_DEMO",10010,2,"seed")])
        archive(self.db, self.path)

    def test_revision_boundary(self):
        for cutoff, rev, price in [(DAY+4,1,10011),(DAY+5,2,10051)]:
            seen = compare(self.db,self.path,60,61,cutoff)
            self.assertEqual(seen["equity"], [("EQ_DEMO",60,rev,price)])

    def test_future_and_upper_bound(self):
        self.assertEqual(compare(self.db,self.path,60,120,60)["rows"],0)
        self.assertEqual(compare(self.db,self.path,60,120,3600)["rows"],1)

    def test_partition_boundary(self):
        self.assertEqual(compare(self.db,self.path,DAY,DAY+1,DAY+1)["files"],["day-1.parquet"])
        self.assertEqual(compare(self.db,self.path,DAY-1,DAY+1,DAY+1)["files"],
                         ["day-0.parquet","day-1.parquet"])

    def test_latest_not_last_arrival(self):
        self.assertEqual(self.db.execute(LATEST,("EQ_DEMO",DAY+5,DAY+5)).fetchone(), (DAY,1,10010))

    def test_missing_asset(self):
        self.assertIsNone(self.db.execute(LATEST,("X",100,100)).fetchone())

    def test_feature_dependencies(self):
        self.assertEqual(equity_feature(self.db,60)["status"], "MISSING_INPUT")
        for cutoff,rev,delta in [(120,1,1),(DAY+5,2,41)]:
            row = equity_feature(self.db,cutoff)
            self.assertEqual(row["inputs"][-1], ("EQ_DEMO",60,rev))
            self.assertAlmostEqual(row["value"], delta/10010)

    def test_corruption(self):
        with (self.path/"day-0.parquet").open("ab") as f:
            f.write(b"changed")
        with self.assertRaisesRegex(ValueError, "checksum"):
            cold_window(self.path,0,1,10)

    def test_rollback(self):
        with self.assertRaises(sqlite3.IntegrityError), self.db:
            self.db.execute("INSERT INTO quotes VALUES ('X',1,1,1,123,2,'seed')")
            self.db.execute("INSERT INTO quotes VALUES ('X',1,1,2,124,2,'seed')")
        self.assertEqual(self.db.execute("SELECT count(*) FROM quotes WHERE asset='X'").fetchone()[0],0)
