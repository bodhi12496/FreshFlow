# Phase 1 methodology

## Reproducible experiment

Run `python freshflow.py` from the repository root using Python 3.12. No packages,
API keys or external datasets are required. Defaults are seed 42, 730 days starting
2023-01-01, a 14-day horizon and 12 validation folds. The default dates are
2023-01-01 through 2024-12-30 inclusive (730 days, not two full calendar years).

The generator uses its own seeded random number generator. Identical settings,
source and Python version produce identical artifacts. `manifest.json` records
settings, Python version, selected model and SHA-256 hashes of source and outputs.
No timestamps or absolute local paths are embedded in the generated files.

## Synthetic demand

The panel contains all combinations of three stores and six products: milk,
bread, salad, sandwich, yogurt and berries. Each has one daily integer demand.
Baseline volumes and synthetic product parameters are declared in `PRODUCTS`;
store volume multipliers are in `STORES`.

Expected demand is the product of baseline volume, store multiplier, annual sine
seasonality, weekend multiplier, linear trend and promotion uplift. Trend grows
by 8% of baseline per 365.25 days. Each consecutive seven-day block has a 20%
probability of a promotion during its first three days; these blocks start at the
dataset's start date, not necessarily Monday. Gaussian noise has standard deviation
18% of expected demand; values are rounded and clipped at zero.

All parameters are illustrative. Demand is not fitted to a retailer. There are no
holidays, substitutions, correlated store shocks, intermittent-demand regimes or
stockout censoring. Unrestricted availability means observed sales equal demand.
These limitations prevent claims of real-world model quality or savings.

### Input schema

| Column | Meaning |
|---|---|
| `date` | ISO calendar date |
| `store_id` | `store_01`, `store_02`, `store_03` |
| `product_id` | One of the six product names |
| `promotion` | Integer 0/1; scheduled synthetic promotion |
| `demand` | Nonnegative integer units |

Validation rejects missing fields, invalid dates, unknown identifiers, missing
series, duplicate keys, gaps, misaligned calendars and invalid counts/flags.
Input row order does not affect chronological evaluation. This phase generates
its own data; a public-data importer is not yet implemented.

## Forecasts and chronological evaluation

1. Seasonal naive repeats the last seven observed daily values for every future week.
2. The 28-day mean repeats the mean of the last 28 observed values.
3. The four-week weekday mean averages the last four observed occurrences of each
   target weekday, repeating those seven means across the horizon.

All models receive the same historical prefix. Predictions are fractional expected
units and are not rounded to orders. Promotion flags are deliberately unused by
these baselines. None of the models accesses actual demand inside its forecast horizon.

For the default run, the first origin is 2024-07-01, using 548 observed days.
Twelve nonoverlapping 14-day validation windows run from 2024-07-02 to 2024-12-16.
The training history expands at every origin: outcomes from earlier completed
windows become available to later forecasts, as they would operationally.

The final 14 days, 2024-12-17 through 2024-12-30, are a separate test window.
The model with lowest pooled validation MAE is selected; ties break alphabetically
by model name. All baselines' test results are shown for transparency, but test
scores do not select the model. Once inspected, this test is no longer an untouched
holdout for future development: later phases need another locked evaluation period.

Nonoverlapping targets avoid counting a demand day in multiple validation windows.
Windows can still be temporally dependent; this phase makes no significance claim.

## Metrics

Let error = prediction − actual, across the forecast rows in a reporting group.

| Metric | Definition |
|---|---|
| MAE | Mean absolute error, in units |
| WAPE (%) | 100 × sum absolute error / sum actual demand |
| Seasonal MASE | Mean of absolute error / origin-specific training scale |
| Bias (units) | Mean signed error; positive = overforecast |
| Bias (%) | 100 × sum signed error / sum actual demand |

The MASE scale for each series and origin is the mean absolute difference between
training observations seven days apart. It uses only training data. A zero scale
makes that forecast row's scaled error undefined; exclude it from MASE, retain it
in other metrics and disclose the included row count as `mase_n`. If every scale
is zero, MASE is undefined. WAPE and percentage bias are undefined when total
actual demand is zero. Undefined values are empty in CSV and `N/A` in the report.

Aggregate MAE and bias pool all forecast rows. WAPE pools demand volume. MASE
averages valid scaled errors across rows; it is not MAE divided by one global
scale. Equal series/window lengths imply equal series weight in MAE and MASE
when every scale is valid, but larger-volume series typically contribute larger
absolute errors. Inspect the series-level metrics alongside pooled results.

## Outputs

| Artifact in `artifacts/` | Purpose |
|---|---|
| `demand.csv` | Generated daily demand and promotion flags |
| `predictions.csv` | Actual/predicted units, cutoff, target date, horizon, model and scale |
| `metrics.csv` | Aggregate metrics by split and model |
| `metrics_by_series.csv` | Store/product diagnostics |
| `metrics_by_horizon.csv` | Accuracy by lead day |
| `metrics_by_fold.csv` | Accuracy stability across chronological windows |
| `report.md` | Human-readable benchmark and validation-selected model |
| `manifest.json` | Run configuration and artifact hashes |

`origin` is the last observed day, and `horizon_day=1` is the following day.
`fold` is one-based; with defaults, fold 13 is test. Each run overwrites these
named files in its output directory. Use separate `--output` directories to
retain multiple runs. Generated files are ignored by Git; a small default report
and manifest are checked in under `reports/` for inspection without execution.

## Checks

`python -m unittest -v` checks hand-calculated forecasts and metrics, zero
denominators, invalid data, seed reproducibility, split boundaries, and artifact
hashes. A future-data perturbation check changes unseen demand and verifies that
forecasts at the earlier origin remain identical. Another check changes test
actuals and verifies validation results and final-test predictions are unchanged.

The GitHub Actions workflow runs those checks and the complete default benchmark.
Local verification used Python 3.12.10; GitHub-hosted CI runs after you push.
