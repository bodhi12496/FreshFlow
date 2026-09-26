"""FreshFlow Phase 1: reproducible daily-demand forecasting using only stdlib."""

import argparse
import csv
import hashlib
import json
import math
import platform
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import fmean


STORES = {"store_01": 0.8, "store_02": 1.0, "store_03": 1.25}
# Mean units, annual amplitude, weekend multiplier, promotion uplift.
# These are synthetic demand parameters, not measured retail estimates.
PRODUCTS = {
    "milk": (85, 0.08, 1.10, 0.25),
    "bread": (65, 0.06, 1.20, 0.30),
    "salad": (32, 0.30, 0.80, 0.45),
    "sandwich": (42, 0.12, 0.65, 0.35),
    "yogurt": (48, 0.15, 1.05, 0.40),
    "berries": (24, 0.40, 1.30, 0.55),
}
MODELS = ("seasonal_naive", "mean_28", "weekday_mean_4")


def generate_data(seed=42, days=730, start=date(2023, 1, 1)):
    """Independent local RNG: same settings and Python version reproduce rows."""
    if type(seed) is not int or type(days) is not int or days < 1:
        raise ValueError("seed must be an integer; days must be a positive integer")
    rng = random.Random(seed)
    rows = []
    for store, store_factor in STORES.items():
        for product, (base, amplitude, weekend, uplift) in PRODUCTS.items():
            for t in range(days):
                day = start + timedelta(days=t)
                # Three-day promotions, scheduled independently of observed demand.
                if t % 7 == 0:
                    promotion_week = rng.random() < 0.20
                promotion = int(promotion_week and t % 7 < 3)
                annual = 1 + amplitude * math.sin(2 * math.pi * t / 365.25)
                weekday = weekend if day.weekday() >= 5 else 1.0
                trend = 1 + 0.08 * t / 365.25
                mean = base * store_factor * annual * weekday * trend
                mean *= 1 + uplift * promotion
                # ponytail: clipped Gaussian counts; replace with count processes
                # before making claims about low-volume or intermittent demand.
                demand = max(0, round(rng.gauss(mean, 0.18 * mean)))
                rows.append({"date": day.isoformat(), "store_id": store,
                             "product_id": product, "promotion": promotion,
                             "demand": demand})
    return rows


def validate_data(rows):
    """Reject incomplete panels, duplicates, gaps, invalid dates and unit counts."""
    groups = defaultdict(dict)
    required = {"date", "store_id", "product_id", "promotion", "demand"}
    for row in rows:
        if not required <= row.keys():
            raise ValueError("Missing required demand columns")
        try:
            day = date.fromisoformat(row["date"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid ISO date") from exc
        if row["store_id"] not in STORES or row["product_id"] not in PRODUCTS:
            raise ValueError("Unknown store or product")
        if type(row["demand"]) is not int or row["demand"] < 0:
            raise ValueError("Demand must be a nonnegative integer")
        if type(row["promotion"]) is not int or row["promotion"] not in (0, 1):
            raise ValueError("Promotion must be 0 or 1")
        key = row["store_id"], row["product_id"]
        if day in groups[key]:
            raise ValueError("Duplicate store/product/date")
        groups[key][day] = row["demand"]
    expected = {(s, p) for s in STORES for p in PRODUCTS}
    if set(groups) != expected:
        raise ValueError("Expected all 18 store-product series")
    reference = sorted(next(iter(groups.values())))
    if any((b - a).days != 1 for a, b in zip(reference, reference[1:])):
        raise ValueError("Missing daily dates")
    series = {}
    for key, values in groups.items():
        if sorted(values) != reference:
            raise ValueError("Series must have the same complete daily calendar")
        series[key] = [values[day] for day in reference]
    return reference, series


def forecast(history, horizon=14):
    """Direct multi-step forecasts; never consume observations inside the horizon."""
    if len(history) < 28 or type(horizon) is not int or horizon < 1:
        raise ValueError("Need at least 28 historical days and a positive horizon")
    if any(not math.isfinite(y) or y < 0 for y in history):
        raise ValueError("History must contain finite, nonnegative demand")
    week = history[-7:]
    weekday_means = [fmean(history[-28 + j::7]) for j in range(7)]
    return {
        "seasonal_naive": [week[h % 7] for h in range(horizon)],
        "mean_28": [fmean(history[-28:])] * horizon,
        "weekday_mean_4": [weekday_means[h % 7] for h in range(horizon)],
    }


def rolling_backtest(dates, series, horizon=14, folds=12):
    """Expanding histories, nonoverlapping validation windows, final test window."""
    if type(horizon) is not int or type(folds) is not int or min(horizon, folds) < 1:
        raise ValueError("horizon and folds must be positive integers")
    first_origin = len(dates) - (folds + 1) * horizon
    if first_origin < 28:
        raise ValueError("Not enough days: need 28 + (folds + 1) * horizon")
    predictions = []
    for fold in range(folds + 1):
        origin = first_origin + fold * horizon
        split = "test" if fold == folds else "validation"
        for (store, product), values in sorted(series.items()):
            if len(values) != len(dates):
                raise ValueError("Series and dates must have equal lengths")
            history = values[:origin]
            scale = fmean(abs(b - a) for a, b in zip(history, history[7:]))
            for model, estimates in forecast(history, horizon).items():
                for h, estimate in enumerate(estimates):
                    predictions.append({
                        "split": split, "fold": fold + 1,
                        "origin": dates[origin - 1].isoformat(),
                        "date": dates[origin + h].isoformat(), "horizon_day": h + 1,
                        "store_id": store, "product_id": product, "model": model,
                        "actual": values[origin + h], "prediction": estimate,
                        "mase_scale": scale,
                    })
    return predictions


def metrics(rows):
    """Pooled unit metrics; undefined ratios are None (blank CSV / null JSON)."""
    if not rows:
        raise ValueError("Cannot score an empty forecast")
    errors = [r["prediction"] - r["actual"] for r in rows]
    actual_sum = sum(r["actual"] for r in rows)
    scaled = [abs(e) / r["mase_scale"] for e, r in zip(errors, rows)
              if r["mase_scale"] > 0]
    return {
        "n": len(rows), "mae": fmean(abs(e) for e in errors),
        "wape_pct": 100 * sum(abs(e) for e in errors) / actual_sum if actual_sum else None,
        "mase": fmean(scaled) if scaled else None,
        "mase_n": len(scaled), "bias_units": fmean(errors),
        "bias_pct": 100 * sum(errors) / actual_sum if actual_sum else None,
    }


def summarize(predictions, dimensions):
    groups = defaultdict(list)
    for row in predictions:
        groups[tuple(row[d] for d in dimensions)].append(row)
    return [dict(zip(dimensions, key), **metrics(rows))
            for key, rows in sorted(groups.items())]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def render_report(scores, selected, dates, horizon, folds, seed):
    first = len(dates) - (folds + 1) * horizon
    lines = [
        "# Phase 1 benchmark", "",
        "Synthetic demand only. These are forecast errors, not inventory benefits.", "",
        f"Seed: **{seed}**. Dataset: **{dates[0]} to {dates[-1]}**, "
        f"**{len(dates) * 18:,} rows**, 3 stores × 6 products.", "",
        f"Validation: **{folds}** nonoverlapping **{horizon}-day** folds, "
        f"**{dates[first]} to {dates[-horizon - 1]}**.",
        f"Final test: **{dates[-horizon]} to {dates[-1]}**. "
        "Each origin uses only demand observed through the previous day.", "",
        f"**Selected on validation MAE: `{selected}`.** "
        "The test set does not choose the winner.", "",
        "| Split | Model | MAE (units) | WAPE (%) | MASE | Bias (units) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for split in ("validation", "test"):
        for row in sorted((s for s in scores if s["split"] == split), key=lambda s: s["mae"]):
            values = ["N/A" if row[k] is None else f"{row[k]:.3f}"
                      for k in ("mae", "wape_pct", "mase", "bias_units")]
            lines.append(f"| {split} | {row['model']} | " + " | ".join(values) + " |")
    lines += ["", "Positive bias means overforecasting; negative means underforecasting.", "",
              "MASE uses the lag-7 absolute error of the training history at each origin. "
              "Zero-scale rows are excluded from MASE only; `mase_n` records its denominator. "
              "WAPE is undefined when total actual demand is zero.", "",
              "Test scores for other baselines are diagnostics only. This one seed and short "
              "test window do not establish statistical superiority or real-world generalisation.", "",
              "Baselines ignore promotion flags. Later models can test whether known promotions "
              "and calendar features improve this benchmark. No stockouts, expiry, cost or ordering "
              "decisions are simulated in Phase 1.", ""]
    return "\n".join(lines)


def run(output, seed=42, days=730, horizon=14, folds=12):
    rows = generate_data(seed, days)
    dates, series = validate_data(rows)
    predictions = rolling_backtest(dates, series, horizon, folds)
    scores = summarize(predictions, ("split", "model"))
    selected = min((r for r in scores if r["split"] == "validation"),
                   key=lambda r: (r["mae"], r["model"]))["model"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "demand.csv": rows, "predictions.csv": predictions, "metrics.csv": scores,
        "metrics_by_series.csv": summarize(predictions, ("split", "model", "store_id", "product_id")),
        "metrics_by_horizon.csv": summarize(predictions, ("split", "model", "horizon_day")),
        "metrics_by_fold.csv": summarize(predictions, ("split", "fold", "model")),
    }
    for name, data in artifacts.items():
        write_csv(output / name, data)
    report = render_report(scores, selected, dates, horizon, folds, seed)
    (output / "report.md").write_text(report, encoding="utf-8")
    manifest = {
        "schema_version": 1, "python_version": platform.python_version(),
        "config": {"seed": seed, "days": days, "start": str(dates[0]),
                   "horizon": horizon, "validation_folds": folds},
        "selected_model": selected, "selection_metric": "validation_mae",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                   for name in [*artifacts, "report.md"]},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts"),
                        help="Generated files are overwritten here (default: artifacts)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--horizon", type=int, default=14)
    parser.add_argument("--folds", type=int, default=12, help="Number of validation windows")
    args = parser.parse_args()
    try:
        print(run(args.output, args.seed, args.days, args.horizon, args.folds))
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
