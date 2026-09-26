# Phase 2: strong forecasting

**Synthetic benchmark — no real-world savings or inventory decisions measured.**

Seed **2026**, **1095 days**, **18 series**, **14-day forecasts**.
Validation: **12 folds**; final rolling test: **12 folds**.
First validation cutoff: **2025-01-28**; first test cutoff: **2025-07-15**.

Frozen validation selections: model **`gb_global`**, baseline **`weekday_mean_4`**.
Final-test MAE improvement over that baseline: **14.631%**.

## All models

| Split | Model | MAE | WAPE (%) | MASE | Bias (units) |
|---|---|---:|---:|---:|---:|
| validation | gb_global | 10.336 | 15.266 | 0.830 | -0.319 |
| validation | gb_local | 10.471 | 15.464 | 0.832 | -0.765 |
| validation | gb_no_promotion | 11.704 | 17.286 | 0.953 | -0.271 |
| validation | weekday_mean_4 | 12.266 | 18.116 | 0.995 | -0.122 |
| validation | mean_28 | 12.376 | 18.279 | 1.026 | -0.122 |
| validation | seasonal_naive | 15.232 | 22.497 | 1.232 | -0.354 |
| test | gb_global | 8.718 | 15.110 | 0.654 | -0.010 |
| test | gb_local | 8.721 | 15.115 | 0.644 | -0.356 |
| test | gb_no_promotion | 9.500 | 16.464 | 0.723 | -0.132 |
| test | weekday_mean_4 | 10.213 | 17.700 | 0.780 | -0.079 |
| test | mean_28 | 10.400 | 18.024 | 0.812 | -0.079 |
| test | seasonal_naive | 12.622 | 21.875 | 0.948 | -0.187 |

## Paired comparisons on the final test

Negative differences favour the candidate. Intervals are exploratory 95% circular moving-block bootstrap intervals over paired daily errors, keeping all stores/products together.

| Candidate | Reference | MAE difference | 95% interval |
|---|---|---:|---|
| seasonal_naive | weekday_mean_4 | 2.409 | [2.024, 2.862] |
| mean_28 | weekday_mean_4 | 0.187 | [-0.108, 0.417] |
| gb_global | weekday_mean_4 | -1.494 | [-1.803, -1.233] |
| gb_no_promotion | weekday_mean_4 | -0.713 | [-0.957, -0.463] |
| gb_local | weekday_mean_4 | -1.492 | [-1.812, -1.227] |
| gb_global | gb_no_promotion | -0.781 | [-0.997, -0.539] |
| gb_global | gb_local | -0.003 | [-0.072, 0.064] |

Block length: 28 days; 2000 resamples. These are intervals for average error differences, not demand forecast intervals. No multiple-comparison correction; no claim of universal statistical superiority.

## Where the validation-selected model helps or hurts

Positive improvement means lower MAE than the validation-selected baseline.

| Dimension | Segment | Cases | Model MAE | Baseline MAE | Improvement (%) |
|---|---|---:|---:|---:|---:|
| store_id | store_01 | 1008 | 6.905 | 8.193 | 15.724 |
| store_id | store_02 | 1008 | 8.553 | 9.975 | 14.256 |
| store_id | store_03 | 1008 | 10.698 | 12.470 | 14.212 |
| product_id | berries | 504 | 4.155 | 5.789 | 28.219 |
| product_id | bread | 504 | 12.459 | 14.531 | 14.257 |
| product_id | milk | 504 | 15.128 | 16.786 | 9.876 |
| product_id | salad | 504 | 5.227 | 6.362 | 17.838 |
| product_id | sandwich | 504 | 7.045 | 8.152 | 13.578 |
| product_id | yogurt | 504 | 8.296 | 9.657 | 14.087 |
| promotion | 0 | 2769 | 8.510 | 9.563 | 11.016 |
| promotion | 1 | 255 | 10.983 | 17.262 | 36.376 |

## Interpretation and limitations

- `gb_global`: one model across all series and horizons, with store/product categories.
- `gb_no_promotion`: the same global approach with the promotion flag removed.
- `gb_local`: one model per store/product, with the same features and hyperparameters.
- Promotion information is assumed scheduled and known 14 days ahead; the ablation measures predictive value, not causal uplift.
- Model choices and hyperparameters stay fixed during test; refits may use earlier test days once observed.
- One synthetic seed, related temporal observations and a simple demand generator limit generalisation.
- Baselines, zero-denominator metric definitions and Phase 1 remain available unchanged.
- Full series, promotion, horizon and fold diagnostics plus training-cutoff audits accompany this report.
