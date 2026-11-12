import unittest
from dataclasses import replace
from news_lab import sample, snapshot, classify

class NewsTests(unittest.TestCase):
    def test_empty_unknown(self):
        self.assertIsNone(snapshot(sample(),4,'EQ_DEMO')['sentiment'])
        self.assertIsNone(classify('未违约。')['score'])
    def test_offsets(self):
        text='甲盈利增长但乙亏损扩大。'
        r=classify(text)
        self.assertEqual(r['score'],0)
        for e in r['evidence']:
            self.assertEqual(text[e['start']:e['end']],e['text'])
    def test_duplicates(self):
        self.assertEqual(snapshot(sample(),7,'EQ_DEMO')['unique_count'],1)
    def test_late(self):
        ids=lambda t: [d['id'] for d in snapshot(sample(),t,'EQ_DEMO')['documents']]
        self.assertNotIn('d1',ids(10)); self.assertIn('d1',ids(12))
    def test_revision(self):
        self.assertLess(snapshot(sample(),10,'EQ_DEMO')['sentiment'],0)
        self.assertEqual(snapshot(sample(),16,'EQ_DEMO')['sentiment'],1)
    def test_future(self):
        x=sample(); a=snapshot(x,10,'EQ_DEMO')
        x[-2]=replace(x[-2],text='未来文字改变')
        self.assertEqual(a,snapshot(x,10,'EQ_DEMO'))
        self.assertEqual(a,snapshot([n for n in x if n.available<=10],10,'EQ_DEMO'))
    def test_withdrawal_is_source_local(self):
        ids=[d['id'] for d in snapshot(sample(),20,'EQ_DEMO')['documents']]
        self.assertNotIn('a1',ids); self.assertIn('copy',ids)
    def test_weight_reference(self):
        got=snapshot(sample(),10,'EQ_DEMO')['sentiment']
        a=2**(-5/10);b=2**(-2/10)
        self.assertAlmostEqual(got,(a-b)/(a+b))
    def test_invalid(self):
        x=sample()
        with self.assertRaises(ValueError): snapshot(x+x[:1],10,'EQ_DEMO')
        with self.assertRaises(ValueError): snapshot(x,10,'EQ_DEMO',0)
    def test_uncertain(self):
        self.assertIsNone(classify('可能违约。')['score'])

if __name__=='__main__': unittest.main()
