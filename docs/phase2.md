# Phase 2 methodology: strong forecasting

## Question and experiment

Does pooling demand across products/stores, using historical patterns and knowing
the promotion schedule improve 14-day forecasts? Compare six fixed approaches:

| Model | Training scope | Purpose |
|---|---|---|
| `seasonal_naive` | Each series | Repeat its most recent observed week |
| `mean_28` | Each series | Repeat its trailing 28-day mean |
| `weekday_mean_4` | Each series | Average the last four matching weekdays |
| `gb_global` | All 18 series and all 14 horizons | Learn common patterns with store/product categories |
| `gb_no_promotion` | Same global training | Remove the explicit target promotion flag |
| `gb_local` | One booster per store/product | Compare pooling with separate models |

The three boosters use scikit-learn's histogram gradient boosting with identical
hyperparameters. Native categorical features represent store and product IDs.
The IDs are categories, not ordinal quantities. Predictions are clipped at zero;
they remain fractional expected units, not order quantities.

This phase uses NumPy, scikit-learn and Matplotlib; SciPy, joblib and threadpoolctl
are scikit-learn dependencies pinned alongside them in `requirements.txt`. There
is no custom model framework or tuning service. Phase 1's implementation and
saved results are preserved.

## Declared protocol and a new evaluation period

`phase2_protocol.json` records the settings chosen before the full benchmark:
seed 2026, 1,095 synthetic days, 14-day horizons, 12 validation folds and 12 test
folds. The runner writes the protocol before generating data or fitting models.
There is no hyperparameter search. This is a locally declared experiment,
not an externally registered research protocol.

| Period | Dates | Role |
|---|---|---|
| Initial history | 2023-01-01 – 2025-01-28 | First expanding training history |
| Validation | 2025-01-29 – 2025-07-15 | 12 × 14-day folds; choose model and baseline |
| Final rolling test | 2025-07-16 – 2025-12-30 | 12 × 14-day folds; evaluate frozen choices |

At each origin, the model sees only completed demand observations. Previous
validation/test outcomes can enter the next refit once their dates have passed.
The selected model, selected baseline and hyperparameters remain fixed across
the entire test period. This is an adaptive-history rolling test, not one static
168-day forecast. Model selection minimises pooled validation MAE; ties use the
alphabetical model name. All models' test scores are disclosed as diagnostics.

The Phase 1 test had already been inspected. Phase 2 therefore uses a different
seed and later evaluation dates. It is a newly generated synthetic panel, **not
an appended version of Phase 1's observations**. Compare methods within Phase 2;
do not interpret differences from the old Phase 1 report as model improvement.
The same synthetic demand mechanism remains a limitation on external validity.

Once these test results have been inspected, they are no longer an untouched
holdout for future tuning. Freeze another evaluation set before subsequent
model development. The `--smoke` command uses a smaller, explicitly labelled
configuration for integration checks; it cannot support résumé performance claims.

## Features and availability

An example is `(store, product, forecast origin, horizon day)`. At an origin with
`c` observed days, demand history is `demand[:c]`; horizon day `h` targets index
`c + h - 1`. A single booster accepts `h` as a feature and predicts that target
directly. Day 14 never consumes actual or recursively predicted demand from days
1–13. Training and prediction use the same feature function.

| Feature family | Features | Available information |
|---|---|---|
| IDs | Store, product categories | Known series identity |
| Horizon | 1–14 | Known forecast lead |
| Lags | Last observed value; origin-relative lag 7, 14, 28 | Observations before the origin |
| Rolling statistics | Mean 7, 28, 56; population standard deviation 28 | Windows ending at the last observed day |
| Weekday history | Last four observed occurrences of the target weekday | All before the origin |
| Calendar | Target weekday sine/cosine, day-of-year sine/cosine, elapsed-day index | Deterministic future calendar |
| Promotion | Target-date 0/1 scheduled flag | Assumed fixed and known at least 14 days ahead |

Lags are **origin-relative**, not blindly shifted relative to the target date.
For example, target-day lag 7 would leak future demand for horizons 8–14.
The weekday feature cycles through already observed weekdays instead.

Synthetic promotions were generated independently of realised demand. Phase 2
explicitly treats the full schedule as available in advance; the generator's
weekly random draws are not a claim about operational announcement dates. A real
dataset needs historical schedule snapshots or announcement timestamps before
this feature is valid. This is an assumption, not information inferred from sales.

Training examples use origins every seven days after a 56-day warm-up. They
include all 14 horizons, so the same target may appear at different training
leads. That is intentional supervised augmentation; evaluation target dates do
not overlap between folds. For each fit, the cached table is filtered to labels
strictly before the current origin. Caching later examples does not authorise
using them. `training_audit.csv` discloses each fit's latest included label date.

Early stopping is disabled because its automatic random split is unsuitable for
this temporal protocol. Trees and all other settings are fixed before testing.
The seven-day training stride is a computational choice, not a tuned result.
It covers only one training-origin weekday; broader origin coverage should be
tested with a daily stride in a new experiment rather than tuned on this test.

## Ablations and interpretation

`gb_global` versus `gb_no_promotion` measures the predictive value of explicitly
knowing the target promotion schedule. The ablated model can still observe past
promotion effects through demand lags, and may infer recurring timing from the
calendar. This is not a causal estimate of sales uplift.

`gb_global` versus `gb_local` compares the same estimator and features with pooled
versus separate training data. Local models have constant ID features and fewer
examples; the whole local system has 18 models. It is a fixed-recipe comparison,
not a claim that every possible local model is inferior.

Segment reports cover store, product, store/product, promotion status, horizon
day and temporal fold. The chosen model is compared with the same validation-chosen
baseline in every segment. We do not cherry-pick a different test winner or
baseline for each product. Negative improvements are retained.

## Statistical comparisons

Metrics reuse Phase 1's MAE, WAPE, lag-7 training-scaled MASE and signed bias.
For paired comparisons, identical forecast cases must match in origin, date,
horizon, store and product, including the actual demand value.

For each target date, average `absolute_error(candidate) - absolute_error(reference)`
across all 18 series. Resample these daily differences using a **circular moving-block
bootstrap**, with 28-day contiguous blocks, 2,000 repetitions and the fixed seed.
Concatenate sampled blocks, truncate to the original period length and compute
the mean. The 2.5th and 97.5th percentiles give an exploratory 95% interval.
Negative differences favour the candidate.

Keeping each day's panel together preserves contemporaneous cross-series
dependence; blocks retain some short-range temporal dependence. The test contains
only six block lengths, so uncertainty estimates remain approximate. Dependence
beyond 28 days and seasonal changes in error differences may violate the bootstrap
approximation. No p-values or multiple-comparison-adjusted significance claims
are supplied. Validation comparisons are selection-biased and exploratory.
An interval crossing zero means the comparison does not clearly distinguish the
methods under this procedure. Fewer than two blocks produces no interval.

These are uncertainty intervals for **mean error differences**, not forecast
intervals for future demand. Quantile forecasting remains Phase 3.

## Reproduce and inspect

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
python phase2.py --smoke
python phase2.py
```

The full run writes to `artifacts/phase2/`; smoke results use
`artifacts/phase2-smoke/`. `--output PATH` changes the destination. Named artifacts
are overwritten on rerun. Relative destinations are resolved from your terminal's
current directory; run from the repository root.

| Output | Contents |
|---|---|
| `demand.csv` | Full synthetic panel |
| `predictions.csv` | Each model's individual out-of-sample forecast and actual |
| `metrics.csv` | Overall validation/test leaderboard |
| `metrics_by_*.csv` | All models by series, store, product, promotion, horizon and fold |
| `paired_comparisons.csv` | Paired MAE differences and bootstrap intervals |
| `segment_comparisons.csv` | Chosen model versus chosen baseline, including regressions |
| `training_audit.csv` | Per-origin label cutoff and pooled training row count |
| `protocol.json`, `manifest.json` | Executed settings, dependency versions and hashes |
| `report.md`, `comparison.png` | Readable findings and static comparison chart |

Small result snapshots are committed under `reports/phase2/`; bulky generated
data and predictions stay ignored. The manifest includes hashes for those
regenerable files even though they are not in the snapshot. Reproducibility is
expected with the same environment; numerical libraries and font rendering can
differ across platforms, so image or floating-point hashes are not a universal
cross-platform guarantee.

## Verification and limitations

Checks cover hand-calculated features, unchanged training arrays and predictions
when unseen demand is modified, promotion-ablation isolation, local-model
isolation, frozen selection, temporal boundaries, bootstrap arithmetic, matching
forecast cases and invalid settings. CI runs all tests, Phase 1 and a Phase 2
smoke benchmark; the full benchmark is a local command.

Demand remains synthetic, uncensored and based on one random seed. There is no
external retail-data validation, inventory simulator, cost saving, forecast
interval or production deployment in Phase 2. These should not be represented
as completed work on a résumé.

## References

- [scikit-learn: histogram gradient boosting](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)
- [scikit-learn: lagged features and time-based evaluation](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html)
