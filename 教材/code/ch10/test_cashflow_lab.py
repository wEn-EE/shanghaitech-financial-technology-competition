import math
import unittest
from cashflow_lab import Bond, solve_ytm, bootstrap_annual, curve_price
from cashflow_lab import select_action, stock_return, credit_zero, gordon


class CashflowTests(unittest.TestCase):
    def test_par_and_premium(self):
        b = Bond()
        self.assertAlmostEqual(b.price(.04), 100., places=10)
        self.assertGreater(b.price(.03), 100.)
        self.assertLess(b.price(.05), 100.)

    def test_zero_coupon_closed_form(self):
        b = Bond(coupon=0., periods=6, frequency=2)
        metrics = b.metrics(.05)
        self.assertAlmostEqual(metrics["dirty"], 100/1.025**6)
        self.assertAlmostEqual(metrics["macaulay"], 3.)
        self.assertAlmostEqual(metrics["convexity"], 3*3.5/1.025**2)

    def test_accrued_and_fractional_time(self):
        b = Bond(elapsed=.5)
        metrics = b.metrics(.03)
        self.assertEqual(metrics["accrued"], 1.)
        self.assertAlmostEqual(metrics["dirty"]-metrics["clean"], 1.)
        self.assertAlmostEqual(metrics["dirty"], Bond().price(.03)*1.015**.5)

    def test_ytm_round_trip_and_negative(self):
        b = Bond()
        for y in (-.01, 0., .03, .3):
            self.assertAlmostEqual(solve_ytm(b, b.price(y)), y, places=10)

    def test_ytm_bracket_failure(self):
        with self.assertRaises(ValueError):
            solve_ytm(Bond(), 1., low=0., high=.1)
        with self.assertRaises(ValueError):
            solve_ytm(Bond(), 100., tolerance=0)

    def test_analytic_derivatives(self):
        b, y, h = Bond(), .03, 1e-4
        v = b.metrics(y)
        derivative = (b.price(y+h)-b.price(y-h))/(2*h)
        second = (b.price(y+h)-2*b.price(y)+b.price(y-h))/h**2
        self.assertTrue(math.isclose(derivative, -v["dirty"]*v["modified"], rel_tol=1e-7))
        self.assertTrue(math.isclose(second, v["dirty"]*v["convexity"], rel_tol=1e-7))

    def test_convexity_and_small_shock(self):
        b, y, dy = Bond(), .03, .001
        v = b.metrics(y)
        linear = v["dirty"]*(1-v["modified"]*dy)
        quad = linear + v["dirty"]*.5*v["convexity"]*dy**2
        self.assertGreater(v["convexity"], 0)
        self.assertLess(abs(quad-b.price(y+dy)), abs(linear-b.price(y+dy)))

    def test_bootstrap_reprices_inputs(self):
        d1,d2 = bootstrap_annual([100.,100.],[.02,.03])
        self.assertAlmostEqual(102*d1, 100.)
        self.assertAlmostEqual(3*d1+103*d2,100.)
        with self.assertRaises(ValueError):
            bootstrap_annual([100.,1.],[.02,.03])

    def test_negative_zero_rate_allowed(self):
        d = bootstrap_annual([101.],[0.])
        self.assertGreater(d[0],1)
        self.assertGreater(curve_price(Bond(coupon=0.), [-.01]*10),100.)

    def test_curve_conversion_and_node_sum(self):
        b,y,h = Bond(),.03,1e-5
        z=2*math.log1p(y/2)
        zeros=[z]*10
        self.assertAlmostEqual(curve_price(b,zeros),b.price(y))
        total=0.
        for i in range(10):
            up,down=zeros.copy(),zeros.copy()
            up[i]+=h; down[i]-=h
            total+=(curve_price(b,down)-curve_price(b,up))/(2*h*b.price(y))
        self.assertAlmostEqual(total,b.metrics(y)["macaulay"],places=7)

    def test_stock_wealth_identity(self):
        self.assertAlmostEqual(stock_return(100,99,dividend=1),0)
        self.assertAlmostEqual(stock_return(99,49.5,split=2),0)
        self.assertAlmostEqual(stock_return(100,49,split=2,dividend=2),0)

    def test_pit_revision_and_unavailable(self):
        versions=[{"id":"D","version":1,"published_at":.2,"received_at":.3},
                  {"id":"D","version":2,"published_at":2.,"received_at":3.}]
        self.assertEqual(select_action(versions,"D",2.5)["version"],1)
        self.assertEqual(select_action(versions,"D",3.)["version"],2)
        with self.assertRaises(LookupError):
            select_action(versions,"D",.25)

    def test_credit_and_boundary(self):
        base=credit_zero(100,.03,0,.4)
        self.assertAlmostEqual(base["spread"],0)
        self.assertLess(credit_zero(100,.03,.02,.4)["price"],base["price"])
        self.assertEqual(credit_zero(100,.03,1,0)["promised_yield"],None)
        with self.assertRaises(ValueError):
            credit_zero(100,.03,1.1,.4)

    def test_invalid_inputs(self):
        for kwargs in ({"face":0},{"coupon":-.1},{"periods":True},{"elapsed":1},{"frequency":0}):
            with self.assertRaises(ValueError):
                Bond(**kwargs)
        for y in (-2.,float("nan")):
            with self.assertRaises(ValueError):
                Bond().price(y)
        with self.assertRaises(ValueError):
            gordon(3,.03,.03)
        with self.assertRaises(ValueError):
            stock_return(100,0)


if __name__ == "__main__":
    unittest.main()
