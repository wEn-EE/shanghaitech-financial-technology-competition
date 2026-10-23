import unittest
import numpy as np
import pandas as pd
from numpy.testing import assert_allclose
from timeseries_lab import (fit_ar1, predict_ar1, simulate, forecast_record,
                            metrics, diagnostics, ASSETS)


class TimeSeriesTests(unittest.TestCase):
    def setUp(self):
        self.data = simulate()
        self.x = self.data.EQ_DEMO.to_numpy()
        self.a = self.data.available_time.to_numpy()

    def test_ols_matches_linear_algebra(self):
        x = self.x[:600]
        beta = np.linalg.lstsq(np.column_stack((np.ones(599), x[:-1])), x[1:], rcond=None)[0]
        fit = fit_ar1(x)
        assert_allclose([fit['c'], fit['phi']], beta, atol=1e-13)

    def test_forecast_three_step_expansion(self):
        m = dict(c=.1, phi=.5, variance=.04)
        mean, var = predict_ar1(m, .8, 3)
        self.assertAlmostEqual(mean, .2 + .5 ** 3 * .6)
        self.assertAlmostEqual(var, .04 * (1 + .25 + .0625))

    def test_white_noise_special_case(self):
        assert_allclose(predict_ar1(dict(c=.2, phi=0., variance=.04), 9., 20), [.2, .04])

    def test_nonfinite_or_constant_rejected(self):
        for x in ([1, 2, np.nan, 4], [1, 1, 1, 1], [1, 2, 3]):
            with self.assertRaises(ValueError):
                fit_ar1(x)

    def test_unstable_not_silently_clipped(self):
        with self.assertRaises(ValueError):
            fit_ar1(np.array([1, 2, 4, 8, 16.]))

    def test_future_mutation_does_not_change_forecast(self):
        baseline = forecast_record(self.x, self.a, 850, 'rolling_ar1', 120)
        changed = self.x.copy()
        changed[850:] = np.nan
        self.assertEqual(baseline, forecast_record(changed, self.a, 850, 'rolling_ar1', 120))

    def test_late_training_input_rejected(self):
        late = self.a.copy()
        late[849] = 850.1
        with self.assertRaises(ValueError):
            forecast_record(self.x, late, 850, 'rolling_ar1', 120)

    def test_fixed_model_still_checks_latest_lag(self):
        late = self.a.copy()
        late[849] = 850.1
        with self.assertRaises(ValueError):
            forecast_record(self.x, late, 850, 'fixed_ar1')

    def test_temporal_order_and_frozen_fit(self):
        a = forecast_record(self.x, self.a, 850, 'fixed_ar1')
        b = forecast_record(self.x, self.a, 900, 'fixed_ar1')
        self.assertEqual(a['phi'], b['phi'])
        self.assertLessEqual(a['train_max_available'], a['fit_cutoff'])
        self.assertLessEqual(a['model_ready'], a['decision_time'])
        self.assertLess(a['decision_time'], 850)

    def test_interval_score_penalty(self):
        f = pd.DataFrame(dict(actual=[0., 2.], mean=[0., 0.], lower=[-1., -1.], upper=[1., 1.]))
        m = metrics(f)
        self.assertEqual(m['coverage95'], .5)
        self.assertEqual(m['interval_score95'], 22.)

    def test_reproducible_and_correlated_panel(self):
        pd.testing.assert_frame_equal(self.data, simulate())
        self.assertEqual(tuple(self.data.columns[-4:]), ASSETS)
        self.assertGreater(self.data[list(ASSETS)].iloc[:600].corr().iloc[0, 1], .15)

    def test_diagnostic_warning_is_retained(self):
        d = diagnostics(self.x[:600])
        self.assertEqual(len(d['acf']), 13)
        self.assertTrue(0 <= d['adf_lags'] <= 8)
        self.assertTrue(any('p-value' in w for w in d['warnings']))


if __name__ == '__main__':
    unittest.main()
