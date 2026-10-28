import copy
import unittest
from datetime import timedelta
import alignment_lab as lab

class AlignmentTests(unittest.TestCase):
    def setUp(self):
        self.rows=lab.samples(); self.cal=lab.sessions(); self.base=self.cal[0]["start"]
    def snap(self,t,rows=None,asset="EQ_DEMO"):
        return lab.snapshot(self.rows if rows is None else rows,asset,
                            self.base+timedelta(seconds=t),self.cal,timedelta(seconds=60))
    def test_offset_equivalence(self):
        self.assertEqual(lab.instant("2026-10-29T09:30:00+08:00"),self.base)
        with self.assertRaises(ValueError):lab.instant("2026-10-29T09:30:00")
    def test_dst_change(self):
        a=lab.local_instant("2026-03-06T09:30:00","America/New_York")
        b=lab.local_instant("2026-03-09T09:30:00","America/New_York")
        self.assertEqual((a.hour,b.hour),(14,13))
    def test_nonexistent_and_ambiguous(self):
        with self.assertRaises(ValueError):
            lab.local_instant("2026-03-08T02:30:00","America/New_York")
        with self.assertRaises(ValueError):
            lab.local_instant("2026-11-01T01:30:00","America/New_York")
        a=lab.local_instant("2026-11-01T01:30:00","America/New_York","earlier")
        b=lab.local_instant("2026-11-01T01:30:00","America/New_York","later")
        self.assertEqual((b-a).total_seconds(),3600)
    def test_calendar_boundaries(self):
        self.assertIsNotNone(lab.session_at(self.base,self.cal))
        self.assertIsNone(lab.session_at(self.cal[0]["end"],self.cal))
        self.assertIsNone(lab.session_at(self.cal[1]["end"],self.cal))
        self.assertIsNone(lab.session_at(self.base+timedelta(days=1),self.cal))
    def test_late_arrival_no_rollback(self):
        self.assertEqual(self.snap(75)["id"],"q4")
        self.assertEqual(self.snap(90)["id"],"q4")
        self.assertEqual(self.snap(60)["id"],"q1")
    def test_stale_and_missing(self):
        self.assertEqual(self.snap(75,asset="GOLD_DEMO")["status"],"MISSING")
        self.assertEqual(self.snap(120,asset="GOLD_DEMO")["status"],"STALE")
        self.assertIsNone(self.snap(120,asset="GOLD_DEMO")["price"])
        self.assertEqual(self.snap(75,asset="BOND_DEMO")["status"],"LIVE")
    def test_session_no_carry(self):
        r=lab.snapshot(self.rows,"EQ_DEMO",self.cal[1]["start"],self.cal,timedelta(days=1))
        self.assertEqual(r["status"],"MISSING")
    def test_bar_boundary_and_revision(self):
        first=lab.bars(self.rows,"EQ_DEMO",self.base+timedelta(seconds=60),self.cal)[0]
        later=lab.bars(self.rows,"EQ_DEMO",self.base+timedelta(seconds=120),self.cal)
        self.assertEqual((first["close"],first["volume"]),(100,2))
        self.assertEqual((later[0]["close"],later[0]["volume"]),(102,5))
        self.assertEqual(later[1]["inputs"],["q3","q4"])
    def test_future_changes_do_not_change_past(self):
        changed=copy.deepcopy(self.rows)
        for r in changed:
            if r["available"]>self.base+timedelta(seconds=60):r["price"]*=10
        self.assertEqual(self.snap(60),self.snap(60,changed))
        self.assertEqual(lab.bars(self.rows,"EQ_DEMO",self.base+timedelta(seconds=60),self.cal),
                         lab.bars(changed,"EQ_DEMO",self.base+timedelta(seconds=60),self.cal))
    def test_partial_bar_and_empty_bar(self):
        self.assertEqual(lab.bars(self.rows,"EQ_DEMO",self.base+timedelta(seconds=59),self.cal),[])
        x=lab.bars([],"EQ_DEMO",self.base+timedelta(seconds=60),self.cal)[0]
        self.assertIsNone(x["close"]);self.assertEqual(x["volume"],0)
    def test_duplicate_validation(self):
        with self.assertRaises(ValueError):lab.validate(self.rows+[self.rows[0]])
    def test_shortened_session_clips_bucket(self):
        cal=[dict(id="SHORT",day="DEMO",start=self.base,end=self.base+timedelta(seconds=90))]
        x=lab.bars(self.rows,"EQ_DEMO",self.base+timedelta(seconds=90),cal)
        self.assertEqual(len(x),2)
        self.assertEqual((x[1]["right"]-x[1]["left"]).total_seconds(),30)

if __name__=="__main__":unittest.main()
