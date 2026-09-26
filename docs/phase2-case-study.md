# FreshFlow Phase 2: what the experiment shows

## The problem

Simple forecasts establish a useful benchmark, but they ignore planned promotions
and may miss product-specific demand patterns. Phase 2 asks whether a richer
model improves forecasting, where the gains occur and whether pooling series is
worthwhile. Inventory outcomes remain a separate, later experiment.

## The approach

- Forecast 18 daily store-product series across 14 lead days.
- Compare three simple baselines with global gradient boosting, separate boosters
  per series and a global booster without the explicit promotion flag.
- Construct every demand feature using only observations available at its origin.
- Select the model and reference baseline on 12 rolling validation windows, then
  freeze those choices before 12 later test windows.
- Report overall and segment errors, along with paired moving-block bootstrap
  intervals that retain daily panel structure and short-term temporal dependence.

## Results of the declared synthetic experiment

The validation-selected global booster achieved **8.718 final-test MAE**, compared
with **10.213** for the selected four-week weekday mean baseline: a **14.6% reduction**.
This covered **3,024 test forecast cases per model** (168 days × 18 series).
The paired MAE difference was **−1.494 units**, with an exploratory 95% interval
of **[−1.803, −1.233]** under the declared 28-day block-bootstrap procedure.

Removing the explicit promotion feature increased global-model MAE to **9.500**.
The full model's advantage was **0.781 units**, suggesting that known schedules
were useful in this synthetic setting. This is not a causal estimate of a
promotion's sales effect.

Pooling was **not a clear forecasting win** over separate models. The global and
local approaches achieved **8.718** and **8.721** MAE; the interval for their
difference, **[−0.072, 0.064]**, crossed zero. The global approach offers one
model per origin instead of eighteen, but no runtime advantage was measured.

The chosen model improved all six aggregate product segments compared with the
chosen baseline. Gains ranged from **9.9% for milk** to **28.2% for berries**.
Promotion-day error fell **36.4%** versus the baseline, compared with **11.0%**
on non-promotion days. These figures concern that particular synthetic sample.

## Why this is useful portfolio evidence

The project demonstrates more than adding a machine-learning algorithm: it
tests information availability, compares pooled and separate learning, isolates
the predictive value of promotion information and exposes uncertainty in model
comparisons. The global/local near-tie is a finding worth explaining, rather than
something to hide behind a leaderboard.

The broad forecasting/inventory problem is established; no claim of a new
algorithm is necessary. Clear implementation, reproducibility and honest
interpretation are the contribution at this stage.

## Résumé wording you can substantiate

> Built a reproducible multi-store demand-forecasting benchmark across 18 synthetic
> time series, using gradient boosting, leakage-safe multi-horizon features and
> rolling backtests; reduced held-out MAE by 14.6% versus a validation-selected
> baseline and evaluated promotion/pooling ablations with paired block-bootstrap
> intervals.

Keep **synthetic** in the wording. Do not turn forecast-error reductions into
claimed cost savings, waste reductions or deployed business impact.

## Interview discussion points

1. Why target-relative lag 7 can leak future demand for a 14-day forecast, and how
   origin-relative features avoid it.
2. Why choosing the winner on test performance would bias the claimed result.
3. Why a pooled model and eighteen local models can have effectively the same
   error, and why operational simplicity is a separate consideration.
4. Why daily blocks are more appropriate than treating every forecast row as an
   independent observation, while still providing only approximate uncertainty.
5. Why forecasting error alone cannot answer how much inventory to order.

## Limitations and next evidence

One synthetic seed, one generator and an assumed advance promotion schedule do
not demonstrate performance at a real retailer. Weekly sampled training origins
also cover only one origin weekday; evaluating different training strides and
origin weekdays would be a useful new, separately held-out experiment. Bootstrap
results rely on their dependence assumptions and are not adjusted for multiple
comparisons. Public retail data, repeated seeds and inventory simulation are
needed before broader conclusions.

Sources: [generated results](../reports/phase2/report.md),
[paired comparisons](../reports/phase2/paired_comparisons.csv),
[segment comparisons](../reports/phase2/segment_comparisons.csv),
[methodology](phase2.md).
