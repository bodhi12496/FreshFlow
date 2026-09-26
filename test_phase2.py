"""Phase 2 checks: hand-calculated features, temporal isolation and comparisons."""

import unittest
from copy import deepcopy
from datetime import date, timedelta

import numpy as np

from freshflow import generate_data
from phase2 import (FEATURES, backtest, block_interval, compare, features, load_protocol,
                    panel, predict_at_origin, samples, select_model, validate_config)


class Phase2Checks(unittest.TestCase):
    @staticmethod
    def config():
        config = load_protocol()
        config.update(days=112, validation_folds=1, test_folds=1, bootstrap_samples=100)
        config["model"]["max_iter"] = 3
        return config

    def test_origin_features_by_hand(self):
        history = list(range(1, 57))
        values = dict(zip(FEATURES, features(history, date(2023, 2, 26), 1, ("store_01", "milk"), 1)))
        self.assertEqual([values[f"lag_{i}"] for i in (1, 7, 14, 28)], [56, 50, 43, 29])
        self.assertEqual([values[f"mean_{i}"] for i in (7, 28, 56)], [53, 42.5, 28.5])
        self.assertEqual(values["weekday_mean_4"], 39.5)
        self.assertEqual(values["promotion"], 1)
        week2 = features(history, date(2023, 3, 5), 8, ("store_01", "milk"), 0)
        self.assertEqual(week2[FEATURES.index("weekday_mean_4")], 39.5)
        with self.assertRaises(ValueError):
            features([float("nan")] * 56, date(2023, 1, 1), 1, ("store_01", "milk"), 0)

    def test_unseen_demand_cannot_change_forecasts_or_training(self):
        config = self.config()
        dates, keys, demand, plans = panel(generate_data(days=config["days"]))
        origin = 84
        cached = samples(dates, keys, demand, plans, 14, 7)
        original, audit = predict_at_origin(dates, keys, demand, plans, origin, config, cached)
        changed = demand.copy()
        changed[:, origin:] = 99999
        changed_samples = samples(dates, keys, changed, plans, 14, 7)
        # The actual training arrays must be identical, not just the resulting metrics.
        mask = cached[3] < origin
        np.testing.assert_array_equal(cached[0][mask], changed_samples[0][mask])
        np.testing.assert_array_equal(cached[1][mask], changed_samples[1][mask])
        mutated, audit2 = predict_at_origin(dates, keys, changed, plans, origin, config, changed_samples)
        for model in original:
            np.testing.assert_array_equal(original[model], mutated[model])
        self.assertEqual(audit, audit2)
        self.assertLess(audit["max_training_target"], str(dates[origin]))

    def test_promotion_ablation_and_local_isolation(self):
        config = self.config()
        dates, keys, demand, plans = panel(generate_data(days=config["days"]))
        origin = 84
        cached = samples(dates, keys, demand, plans, 14, 7)
        original, _ = predict_at_origin(dates, keys, demand, plans, origin, config, cached)
        new_plans = plans.copy()
        new_plans[:, origin:] = 1 - new_plans[:, origin:]
        mutated, _ = predict_at_origin(dates, keys, demand, new_plans, origin, config, cached)
        np.testing.assert_array_equal(original["gb_no_promotion"], mutated["gb_no_promotion"])
        changed = demand.copy()
        changed[1:] *= 10  # Other series must never enter the first local model.
        changed_cache = samples(dates, keys, changed, plans, 14, 7)
        local, _ = predict_at_origin(dates, keys, changed, plans, origin, config, changed_cache)
        np.testing.assert_array_equal(original["gb_local"][0], local["gb_local"][0])

    def test_bootstrap_arithmetic_and_matching(self):
        self.assertEqual(block_interval([-2] * 84, 28, 100, 42), (-2, -2))
        self.assertEqual(block_interval([1] * 14, 28, 100, 42), (None, None))
        self.assertEqual(block_interval(list(range(84)), 28, 100, 42),
                         block_interval(list(range(84)), 28, 100, 42))
        rows = []
        for i in range(84):
            for model, value in (("candidate", 11), ("baseline", 13)):
                rows.append({"split": "test", "model": model, "origin": "2022-12-31",
                             "date": str(date(2023, 1, 1) + timedelta(days=i)), "horizon_day": i + 1,
                             "store_id": "s", "product_id": "p", "actual": 10, "prediction": value})
        result = compare(rows, "candidate", "baseline", "test", self.config())
        self.assertEqual((result["mae_difference"], result["ci95_low"], result["ci95_high"]), (-2, -2, -2))
        with self.assertRaises(ValueError):
            compare(rows[:-1], "candidate", "baseline", "test", self.config())
        with self.assertRaises(ValueError):
            compare(rows + [rows[0]], "candidate", "baseline", "test", self.config())

    def test_complete_backtest_and_frozen_selection(self):
        config = self.config()
        predictions, audits, selected, baseline = backtest(generate_data(days=config["days"]), config)
        self.assertEqual(len(predictions), 18 * 14 * 2 * 6)
        self.assertEqual(len(audits), 2)
        self.assertTrue(all(np.isfinite(r["prediction"]) and r["prediction"] >= 0 for r in predictions))
        self.assertTrue(all(r["origin"] < r["date"] for r in predictions))
        validation_dates = {r["date"] for r in predictions if r["split"] == "validation"}
        test_dates = {r["date"] for r in predictions if r["split"] == "test"}
        self.assertTrue(validation_dates.isdisjoint(test_dates))
        poisoned = deepcopy(predictions)
        for row in poisoned:
            if row["split"] == "test":
                row["prediction"] = row["actual"] if row["model"] != selected else 99999
        candidates = {r["model"] for r in predictions}
        self.assertEqual(select_model(poisoned, candidates), selected)
        self.assertIn(baseline, ("seasonal_naive", "mean_28", "weekday_mean_4"))

    def test_invalid_protocol(self):
        for key, value in (("days", 60), ("horizon", 0), ("test_folds", -1),
                           ("training_stride", 0), ("bootstrap_samples", 0), ("seed", -1)):
            config = self.config()
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(config)
        config = self.config()
        config["model"]["early_stopping"] = True
        with self.assertRaises(ValueError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
