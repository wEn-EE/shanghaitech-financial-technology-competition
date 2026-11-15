import unittest
import numpy as np
from validation_lab import data, train_ids, fit, predict, select, experiment

class ValidationTests(unittest.TestCase):
    def test_maturity(self):
        _,_,r=data()
        ids=train_ids(r,80)
        self.assertEqual(ids[-1],75)
        self.assertTrue(np.all(r[ids]<80))
    def test_constant_removed(self):
        x,y,_=data();m=fit(x[:70],y[:70],'raw')
        self.assertNotIn(4,m['selected'])
    def test_pca_orthogonal(self):
        x,y,_=data();m=fit(x[:70],y[:70],'pca2');v=np.array(m['components'])
        np.testing.assert_allclose(v.T@v,np.eye(2),atol=1e-12)
    def test_reconstruction(self):
        x,y,_=data();m=fit(x[:70],y[:70],'pca1')
        a=((x[:70]-m['mean'])/m['scale'])[:,m['selected']];v=np.array(m['components'])
        self.assertAlmostEqual(float(np.sum((a-a@v@v.T)**2)),m['singular'][1]**2)
    def test_raw_full_pca(self):
        x,y,_=data()
        a=fit(x[:70],y[:70],'raw');b=fit(x[:70],y[:70],'pca2')
        np.testing.assert_allclose(predict(a,x[70:80]),predict(b,x[70:80]),atol=1e-12)
    def test_future_test_mutation(self):
        x,y,r=data();a=experiment(x,y,r)
        x[200:]*=100;y[200:]+=999
        b=experiment(x,y,r)
        self.assertEqual(a['chosen'],b['chosen']);self.assertEqual(a['model'],b['model'])
        self.assertEqual(a['trials'],b['trials'])
    def test_unmatured_labels(self):
        x,y,r=data();tr=train_ids(r,80);a=fit(x[tr],y[tr],'pca1')
        y[76:]+=999
        self.assertEqual(a,fit(x[tr],y[tr],'pca1'))
    def test_generator_prefix(self):
        a=data(100);b=data(240)
        for i in range(3): np.testing.assert_array_equal(a[i],b[i][:100])
    def test_invalid(self):
        x,y,_=data()
        with self.assertRaises(ValueError):fit(x[:20],y[:20],'invalid')

if __name__=='__main__':unittest.main()
