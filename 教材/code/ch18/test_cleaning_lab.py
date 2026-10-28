import copy
import math
import unittest
import cleaning_lab as lab

class CleaningTests(unittest.TestCase):
    def test_counts_and_conservation(self):
        r=lab.clean(lab.samples())
        self.assertEqual(r["counts"], dict(OBSERVED=90,DUPLICATE=1,IMPUTED=2,
                                          MISSING=1,QUARANTINE=3,FLAGGED=1))
        self.assertEqual(len(r["audit"]),98)
        self.assertEqual(len(r["output"]),94)

    def test_input_unchanged(self):
        x=lab.samples(); before=copy.deepcopy(x); lab.clean(x)
        self.assertEqual(x,before)

    def test_fill_age_and_no_fabricated_return(self):
        eq={r["t"]:r for r in lab.clean(lab.samples())["output"] if r["asset"]=="EQ_DEMO"}
        self.assertEqual([eq[t]["age"] for t in (9,10,11)],[1,2,3])
        self.assertEqual(eq[9]["view_price"],eq[8]["raw_price"])
        self.assertIsNone(eq[11]["view_price"])
        for t in (9,10,11,12):
            self.assertIsNone(eq[t]["log_return"])

    def test_real_jump_is_retained(self):
        x=next(r for r in lab.clean(lab.samples())["output"] if r["asset"]=="EQ_DEMO" and r["t"]==16)
        self.assertEqual(x["status"],"FLAGGED")
        self.assertEqual(x["view_price"],x["raw_price"])
        self.assertAlmostEqual(x["log_return"],math.log(.92)+.001)

    def test_prefix_invariance(self):
        rows=lab.samples()
        n=52
        self.assertEqual(lab.clean(rows[:n])["output"],
                         lab.clean(rows)["output"][:len(lab.clean(rows[:n])["output"])])
        altered=copy.deepcopy(rows)
        for r in altered[n:]:
            if r["price"] is not None: r["price"]*=50
        self.assertEqual(lab.clean(rows)["audit"][:n],lab.clean(altered)["audit"][:n])

    def test_duplicate_does_not_change_state(self):
        rows=lab.samples()[:30]; base=lab.clean(rows)
        rows.insert(10,copy.deepcopy(rows[9]))
        got=lab.clean(rows)
        strip=lambda rr:[{k:v for k,v in x.items() if k!="source_receipt"} for x in rr["output"]]
        self.assertEqual(strip(base),strip(got))

    def test_hard_errors_break_return(self):
        r=lab.clean(lab.samples())
        for asset in ("BOND_DEMO","GOLD_DEMO"):
            x=next(x for x in r["output"] if x["asset"]==asset and x["t"]==13)
            self.assertIsNone(x["log_return"])

    def test_zero_mad_has_finite_score(self):
        rows=[dict(asset="EQ_DEMO",t=t,available=t,unit="CNY/share",price=100 if t<8 else 110)
              for t in range(9)]
        r=lab.clean(rows)["output"][-1]
        self.assertTrue(math.isfinite(r["score"]))
        self.assertEqual(r["status"],"FLAGGED")

    def test_order_not_silently_sorted(self):
        rows=[x for x in lab.samples() if x["asset"]=="FX_DEMO"][:3]
        rows[1],rows[2]=rows[2],rows[1]
        self.assertEqual(lab.clean(rows)["audit"][-1]["reason"],"ORDER_REQUIRES_REPLAY")

    def test_all_missing_stays_missing(self):
        rows=[dict(asset="EQ_DEMO",t=t,available=t,unit="CNY/share",price=None) for t in range(5)]
        self.assertTrue(all(x["view_price"] is None for x in lab.clean(rows)["output"]))

if __name__=="__main__":
    unittest.main()
