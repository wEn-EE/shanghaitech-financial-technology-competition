import unittest
import numpy as np
from process_lab import (transition_matrix, stationary_two, simulate_chain,
                         fit_transitions, conditional_nll, brownian_checks)


class ProcessTests(unittest.TestCase):
    def test_validation(self):
        for p in [[[.9,.2],[.2,.8]], [[1.1,-.1],[0,1]], [[np.nan,0],[0,1]]]:
            with self.assertRaises(ValueError): transition_matrix(p)

    def test_stationary_and_finite_horizon(self):
        p=np.array([[.96,.04],[.2,.8]])
        pi=stationary_two(p)
        np.testing.assert_allclose(pi,[5/6,1/6])
        np.testing.assert_allclose(pi@p,pi)
        for h in [1,5,20]:
            np.testing.assert_allclose(np.linalg.matrix_power(p,h)[0,1],(1-.76**h)/6)

    def test_nonunique_and_periodic(self):
        with self.assertRaises(ValueError): stationary_two(np.eye(2))
        p=np.array([[0,1],[1,0]])
        np.testing.assert_equal(np.linalg.matrix_power(p,2),np.eye(2))
        np.testing.assert_allclose(stationary_two(p),[.5,.5])

    def test_counts_boundary(self):
        x=np.array([0,0,1,1,0,1])
        p,c=fit_transitions(x[:4],alpha=0)
        np.testing.assert_equal(c,[[1,1],[0,1]])
        np.testing.assert_allclose(p,[[.5,.5],[0,1]])
        y=x.copy();y[4:]=0
        np.testing.assert_equal(fit_transitions(y[:4])[0],fit_transitions(x[:4])[0])

    def test_unseen_row_and_smoothing(self):
        with self.assertRaises(ValueError):fit_transitions(np.array([0,0]),alpha=0)
        p,_=fit_transitions(np.array([0,0]),alpha=.5)
        np.testing.assert_allclose(p,[[.75,.25],[.5,.5]])
        with self.assertRaises(ValueError):fit_transitions([0.,1.])

    def test_impossible_observation(self):
        self.assertEqual(conditional_nll([0,1],np.eye(2)),float('inf'))

    def test_reproduction(self):
        p=[[.96,.04],[.2,.8]]
        a=simulate_chain(p,50,0,np.random.default_rng(9))
        b=simulate_chain(p,50,0,np.random.default_rng(9))
        np.testing.assert_array_equal(a,b)

    def test_quadratic_variation_and_ito_identity(self):
        r=brownian_checks(np.random.default_rng(7),paths=2000)
        self.assertLess(r['discrete_identity_max_error'],1e-11)
        self.assertLess(abs(r['qv']['1024']['mean']-1),.01)
        self.assertLess(abs(r['qv']['1024']['rmse']/np.sqrt(2/1024)-1),.15)
        self.assertLess(abs(r['right_sum_mean']-r['left_integral_mean']-1),.01)


if __name__=='__main__': unittest.main()
