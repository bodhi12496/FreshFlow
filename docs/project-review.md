# Project assessment and recommended direction

## Is this a good project?

Yes. The business decision is specific, the trade-offs are measurable, and the
phases connect forecasting to uncertainty, operations and optimisation. A clean
benchmark makes later improvements credible. A recruiter can inspect assumptions,
reproduce the experiment and see what each added component contributes.

Phases 1–2 establish and compare forecasting methods; they do not yet answer the project's inventory
question. That answer requires the simulator, policies and controlled experiments.

## Is it unique?

The broad idea and central question are established. The 2025 research paper
[Forecast accuracy and inventory performance: Insights on their relationship from
the M5 competition data](https://www.sciencedirect.com/science/article/pii/S0377221724009755)
studies the relationship between forecast accuracy and inventory performance.
Position FreshFlow as a reproducible portfolio investigation, not a novel claim
that nobody has connected forecasting and stock control before.

There is also an existing company called [Freshflow](https://freshflow.ai/)
working on fresh-product forecasting and replenishment. Consider choosing a more
distinctive portfolio name before publishing widely. The repository name has
been preserved; this is a branding suggestion, not a legal assessment or a claim
that any alternative name is available.

## Focused improvements

1. **Make the forecast × policy experiment the centrepiece.** Evaluate each model
   with each policy on identical demand paths, initial inventory and constraints.
   Keep costs and service definitions fixed. This separates model improvements
   from decision-rule improvements and reveals ranking reversals.
2. **Compare cost and waste at comparable service levels.** Tune policy settings
   on validation scenarios. On held-out scenarios, show cost–service and
   waste–service trade-offs; otherwise a cheaper policy might simply lose more sales.
3. **Treat availability as part of the data story.** Later distinguish latent demand
   from sales censored by stockouts. Use known latent demand in synthetic experiments
   to measure the distortion before attempting an estimated correction on public data.
4. **Keep public data and invented operations separate.** The
   [M5 dataset](https://www.kaggle.com/competitions/m5-forecasting-accuracy/data)
   is a candidate for external sales-forecast evaluation. Do not claim it supplies
   verified expiry dates, usable inventory or all operational costs. Document any
   mapping to perishable-product scenarios and label simulated business outcomes.
5. **Use repeated, paired experiments in Phase 6.** Reuse demand paths across
   competing methods within each seed and repeat across seeds. Report uncertainty
   for paired cost/waste differences, sensitivity to shelf life and lead time, and
   failures as well as wins. Avoid picking the most flattering seed.

## Changes already incorporated into Phase 1

- Separate validation selection from the final test period.
- Keep training-only scaling and direct multi-step forecasts free of future data.
- Report both pooled and store/product, horizon and fold diagnostics.
- Record configuration and checksums so results can be regenerated and audited.
- Define zero-denominator metrics and disclose synthetic-data limitations.

## Phase 2 delivered and next steps

Phase 2 now includes global/local gradient boosting, a promotion ablation,
origin-safe features, a later rolling test and paired error intervals. See the
[case study](phase2-case-study.md) for the measured results and their limitations.

Next, Phase 3 should add quantile forecasts and temporal calibration using
separate training, calibration and final evaluation periods. Keep these point
forecasters as comparators. Add external retail data before describing the
results as real-world forecasting performance; inventory benefits still require
the simulator and policy experiments in later phases.

The portfolio contribution should be the evidence: which forecasting improvements
survive realistic inventory constraints, and under which assumptions they stop helping.
