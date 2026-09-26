# Phase 1 benchmark

Synthetic demand only. These are forecast errors, not inventory benefits.

Seed: **42**. Dataset: **2023-01-01 to 2024-12-30**, **13,140 rows**, 3 stores × 6 products.

Validation: **12** nonoverlapping **14-day** folds, **2024-07-02 to 2024-12-16**.
Final test: **2024-12-17 to 2024-12-30**. Each origin uses only demand observed through the previous day.

**Selected on validation MAE: `mean_28`.** The test set does not choose the winner.

| Split | Model | MAE (units) | WAPE (%) | MASE | Bias (units) |
|---|---|---:|---:|---:|---:|
| validation | mean_28 | 9.984 | 18.786 | 0.796 | 0.514 |
| validation | weekday_mean_4 | 10.036 | 18.884 | 0.784 | 0.514 |
| validation | seasonal_naive | 12.642 | 23.787 | 0.974 | 0.328 |
| test | weekday_mean_4 | 10.986 | 18.468 | 0.869 | -3.413 |
| test | mean_28 | 11.164 | 18.766 | 0.894 | -3.413 |
| test | seasonal_naive | 13.663 | 22.967 | 1.060 | -0.536 |

Positive bias means overforecasting; negative means underforecasting.

MASE uses the lag-7 absolute error of the training history at each origin. Zero-scale rows are excluded from MASE only; `mase_n` records its denominator. WAPE is undefined when total actual demand is zero.

Test scores for other baselines are diagnostics only. This one seed and short test window do not establish statistical superiority or real-world generalisation.

Baselines ignore promotion flags. Later models can test whether known promotions and calendar features improve this benchmark. No stockouts, expiry, cost or ordering decisions are simulated in Phase 1.
