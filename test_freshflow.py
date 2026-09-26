"""Run with: python -m unittest -v (no third-party test dependencies)."""

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

from freshflow import forecast, generate_data, metrics, rolling_backtest, run, validate_data


class FoundationChecks(unittest.TestCase):
    def test_seed_and_complete_panel(self):
        rows = generate_data(days=60)
        self.assertEqual(rows, generate_data(days=60))
        self.assertNotEqual(rows, generate_data(seed=43, days=60))
        dates, series = validate_data(rows)
        self.assertEqual((len(rows), len(dates), len(series)), (1080, 60, 18))
        self.assertEqual(validate_data(list(reversed(rows))), (dates, series))

    def test_invalid_data_rejected(self):
        rows = generate_data(days=60)
        invalid = [[], rows + [rows[0]], rows[1:],
                   [r for r in rows if r["date"] != "2023-01-10"],
                   [r for r in rows if r["product_id"] != "milk"]]
        for field, value in (("demand", -1), ("demand", float("nan")),
                             ("demand", 1.5), ("date", "2023-02-30"),
                             ("promotion", 2), ("store_id", "unknown")):
            altered = deepcopy(rows)
            altered[0][field] = value
            invalid.append(altered)
        missing = deepcopy(rows)
        del missing[0]["demand"]
        invalid.append(missing)
        for sample in invalid:
            with self.subTest(sample=sample[:1]), self.assertRaises(ValueError):
                validate_data(sample)

    def test_baselines_by_hand(self):
        result = forecast(list(range(1, 29)), 15)
        self.assertEqual(result["seasonal_naive"], list(range(22, 29)) * 2 + [22])
        self.assertEqual(result["mean_28"], [14.5] * 15)
        self.assertEqual(result["weekday_mean_4"],
                         [11.5 + j for j in range(7)] * 2 + [11.5])
        for history in ([1] * 27, [float("nan")] * 28, [-1] * 28):
            with self.assertRaises(ValueError):
                forecast(history)

    def test_rolling_boundaries_and_future_leakage(self):
        dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(70)]
        values = list(range(70))
        rows = rolling_backtest(dates, {("s", "p"): values}, folds=2)
        validation = {r["date"] for r in rows if r["split"] == "validation"}
        test = {r["date"] for r in rows if r["split"] == "test"}
        self.assertTrue(validation.isdisjoint(test))
        self.assertEqual((len(validation), len(test)), (28, 14))
        self.assertTrue(all(r["date"] > r["origin"] for r in rows))
        self.assertEqual(rows[0]["mase_scale"], 7)
        # Alter all observations after the first origin: its forecasts stay fixed.
        changed = rolling_backtest(dates, {("s", "p"): values[:28] + [9999] * 42}, folds=2)
        for original, mutated in zip(rows, changed):
            if original["fold"] == 1:
                self.assertEqual(original["prediction"], mutated["prediction"])
                self.assertEqual(original["mase_scale"], mutated["mase_scale"])
        # Alter only the final test: validation scores and test predictions stay fixed.
        changed = rolling_backtest(dates, {("s", "p"): values[:56] + [9999] * 14}, folds=2)
        self.assertEqual([r for r in rows if r["split"] == "validation"],
                         [r for r in changed if r["split"] == "validation"])
        self.assertEqual([r["prediction"] for r in rows], [r["prediction"] for r in changed])
        with self.assertRaises(ValueError):
            rolling_backtest(dates[:30], {("s", "p"): values[:30]}, folds=2)

    def test_metric_arithmetic_and_zero_denominators(self):
        rows = [{"actual": 10, "prediction": 12, "mase_scale": 2},
                {"actual": 20, "prediction": 16, "mase_scale": 4}]
        score = metrics(rows)
        self.assertEqual((score["mae"], score["wape_pct"], score["mase"],
                          score["bias_units"]), (3, 20, 1, -1))
        self.assertAlmostEqual(score["bias_pct"], -100 / 15)
        zeros = metrics([{"actual": 0, "prediction": 2, "mase_scale": 0}])
        self.assertEqual((zeros["mae"], zeros["mase_n"]), (2, 0))
        self.assertIsNone(zeros["wape_pct"])
        self.assertIsNone(zeros["mase"])
        self.assertIsNone(zeros["bias_pct"])
        mixed = metrics(rows + [{"actual": 0, "prediction": 2, "mase_scale": 0}])
        self.assertEqual((mixed["mase"], mixed["mase_n"], mixed["n"]), (1, 2, 3))

    def test_end_to_end_artifact_reproducibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            a, b = Path(temporary) / "a", Path(temporary) / "b"
            run(a, days=70, folds=2)
            run(b, days=70, folds=2)
            self.assertEqual(len(list(a.iterdir())), 8)
            for path in a.iterdir():
                self.assertEqual(path.read_bytes(), (b / path.name).read_bytes())
            manifest = json.loads((a / "manifest.json").read_text())
            for name, digest in manifest["sha256"].items():
                self.assertEqual(hashlib.sha256((a / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
