import unittest
import json
from lineage_lab import connect, pipeline, sample, verify, canonical, digest

class LineageTests(unittest.TestCase):
    def setUp(self): self.db=connect(':memory:')
    def tearDown(self): self.db.close()
    def test_canonical(self):
        self.assertEqual(canonical({'a':1,'b':2}),canonical({'b':2,'a':1}))
    def test_retry(self):
        a=pipeline(self.db,sample(),3);b=pipeline(self.db,sample(),3)
        self.assertTrue(b['cached']);self.assertEqual(a['manifest_hash'],b['manifest_hash'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)
    def test_pit(self):
        a=pipeline(self.db,sample(),3);b=pipeline(self.db,sample(),8)
        self.assertEqual(a['result']['selected_ids'],['a','b'])
        self.assertEqual(b['result']['mean'],'4')
        self.assertNotEqual(a['recipe_hash'],b['recipe_hash'])
    def test_failure_rollback(self):
        with self.assertRaises(RuntimeError):pipeline(self.db,sample(),3,fail=True)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT status FROM runs').fetchone()[0],'FAILED')
        self.assertFalse(pipeline(self.db,sample(),3)['cached'])
    def test_corruption(self):
        a=pipeline(self.db,sample(),3)
        self.db.execute('UPDATE artifacts SET body=? WHERE hash=?',(b'bad',digest(sample())))
        self.db.commit()
        with self.assertRaises(ValueError):pipeline(self.db,sample(),3)
    def test_input_change(self):
        a=pipeline(self.db,sample(),3)
        rows=json.loads(sample());rows[0]['value']='9'
        b=pipeline(self.db,canonical(rows),3)
        self.assertNotEqual(a['recipe_hash'],b['recipe_hash'])
        self.assertEqual(verify(self.db,a['manifest_hash'])['mean'],'2')
    def test_future_change(self):
        a=pipeline(self.db,sample(),3);rows=json.loads(sample());rows[-1]['value']='99'
        b=pipeline(self.db,canonical(rows),3)
        self.assertNotEqual(a['recipe_hash'],b['recipe_hash'])
        self.assertEqual(a['result'],b['result'])
    def test_recompute(self):
        a=pipeline(self.db,sample(),3)
        other=connect(':memory:')
        try:self.assertEqual(a['manifest_hash'],pipeline(other,sample(),3)['manifest_hash'])
        finally:other.close()
    def test_unknown(self):
        self.assertEqual(pipeline(self.db,sample(),0)['result']['state'],'UNKNOWN')
    def test_invalid(self):
        rows=json.loads(sample());rows.append(rows[0])
        with self.assertRaises(ValueError):pipeline(self.db,canonical(rows),3)
        with self.assertRaises(ValueError):pipeline(self.db,sample(),3,'NaN')

if __name__=='__main__':unittest.main()
