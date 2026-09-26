# FreshFlow

### Demand forecasting and inventory optimisation for perishable products

FreshFlow is a Python project exploring how demand forecasts can support better inventory decisions.

The goal is to build a system that forecasts demand, estimates uncertainty and recommends replenishment quantities while considering product expiry, delivery lead times and operational constraints.

> **Project status:** Phase 1 implemented and locally verified. Reproducible synthetic data, three baseline forecasts, rolling validation and a separate final test are available. Inventory simulation and order recommendations are planned for later phases.

## Run Phase 1

Use **Python 3.12**. There are no third-party dependencies or installation steps.
From the repository root:

```bash
python3 -m unittest -v
python3 freshflow.py
```

On Windows, use `py -3.12` instead of `python3` if needed.

The default run generates **13,140 demand rows** across 18 series, evaluates
**12 rolling 14-day validation windows** and a **separate 14-day final test**,
and writes CSV results, a Markdown report and a checksum manifest to `artifacts/`.
The command also prints the report. Re-running replaces files in that directory.

```bash
python3 freshflow.py --seed 43 --output artifacts/seed43
python3 freshflow.py --help
```

Read the [default benchmark](reports/phase1.md), [methodology and data dictionary](docs/phase1.md),
and [project assessment and proposed improvements](docs/project-review.md).

The default validation MAE selects the **28-day mean** (9.984 units); its final-test
MAE is **11.164 units**. The four-week weekday mean has a slightly lower test MAE
(10.986), but the selection remains based on validation. These are single-seed
synthetic benchmark results, not evidence of inventory savings.

## Repository Layout

```text
freshflow.py             # Generation, validation, forecasts, evaluation and CLI
test_freshflow.py       # Standard-library checks (run via unittest)
docs/phase1.md          # Data assumptions, split protocol and metric definitions
docs/project-review.md  # Positioning, naming and next-phase recommendations
reports/phase1.md       # Checked-in default benchmark
reports/manifest.json  # Configuration and hashes for that benchmark
.github/workflows/ci.yml # Tests and complete benchmark on push/PR
```

Generated `artifacts/` and Python caches are ignored by Git. The small report
snapshot is committed so readers can inspect results without running the code.
GitHub Actions is configured; its remote run will happen after the files are pushed.

## The Problem

For businesses selling perishable products, inventory decisions involve a difficult trade-off:

- Ordering too little leads to stockouts and lost sales.
- Ordering too much increases holding costs and product waste.
- Products expire, deliveries take time and storage capacity is limited.
- Future demand is uncertain and varies across products, stores and seasons.

A demand forecast alone does not determine the right order quantity. A useful replenishment decision must also account for inventory availability, expiry, incoming deliveries and business costs.

FreshFlow aims to connect these elements in one reproducible workflow.

## The Core Question

**Does a more accurate forecast always lead to a better inventory decision?**

FreshFlow will investigate this by comparing forecasting models and replenishment policies using both prediction metrics and operational outcomes.

The project will examine where improvements come from:

- Better demand predictions.
- Better estimates of uncertainty.
- Better ordering decisions under constraints.

## A Simple Example

Suppose a store forecasts demand for 100 units of milk tomorrow.

The appropriate order quantity also depends on:

- How many usable units are already available.
- Which batches are approaching expiry.
- Whether another delivery is arriving.
- How uncertain tomorrow's demand is.
- The costs of excess stock and unmet demand.

FreshFlow will use this information to evaluate replenishment decisions and their expected consequences.

## Project Roadmap

| Phase | Focus | Key Deliverables |
|---|---|---|
| 1 — implemented | Forecasting foundation | Synthetic data, validation checks, baseline models and rolling backtesting |
| 2 | Advanced forecasting | Feature engineering, statistical and machine learning models, segment-level diagnostics |
| 3 | Forecast uncertainty | Quantile forecasts, interval calibration and demand scenarios |
| 4 | Inventory simulation | Stock movements, expiry, deliveries, lost sales and cost accounting |
| 5 | Replenishment optimisation | Ordering policies and constrained optimisation under uncertain demand |
| 6 | Experiments and evaluation | Forecast-policy comparisons, stress tests and sensitivity analysis |
| 7 | Interactive application | A planner interface, visual explanations and a reproducible demonstration |

## Initial Scope

The initial forecasting experiment uses:

- Three stores.
- Six perishable products per store.
- Eighteen daily store-product time series.
- A 14-day forecasting horizon.
- Synthetic demand with weekday patterns, seasonality, trend and promotions.

The starting baselines are:

1. **Seasonal naive:** Repeat the most recent observed week.
2. **28-day mean:** Forecast the average demand from the previous 28 days.
3. **Four-week weekday mean:** Average demand from the previous four occurrences of the same weekday.

These establish a benchmark before introducing more complex models.

## Planned Methodology

### Demand Forecasting

Compare simple baselines with statistical and machine learning approaches.

Candidate features include historical demand, lagged values, rolling statistics, calendar variables and promotions known at prediction time.

### Uncertainty Estimation

Develop probabilistic forecasts to describe a range of possible demand outcomes.

Evaluate whether forecast intervals provide useful coverage and whether demand scenarios improve inventory decisions.

### Inventory Simulation

Build a daily simulator that tracks:

- Inventory by batch and expiry date.
- Outstanding orders and deliveries.
- Fulfilled demand and lost sales.
- Expired stock.
- Procurement, holding, disposal and shortage costs.

### Optimisation

Compare simple ordering rules with constrained optimisation approaches.

Planned constraints include lead times, storage capacity, supplier limits and purchasing budgets.

## Evaluation

FreshFlow will evaluate prediction quality and decision quality separately.

| Area | Planned Metrics |
|---|---|
| Point forecasts | MAE, WAPE, seasonal MASE and forecast bias |
| Probabilistic forecasts | Pinball loss, interval coverage and interval width |
| Inventory outcomes | Total cost, unit fill rate, expired units and waste rate |
| Operational feasibility | Constraint violations and optimisation runtime |

Phase 1 uses chronological rolling backtests. Model selection uses validation MAE, with a separate final test period. Later phases must lock a new holdout before development, because the Phase 1 test has now been inspected.

## Data and Assumptions

The initial dataset is synthetic and intended for development, learning and controlled experiments.

In the first phase, product availability is unrestricted, so observed sales equal demand. Later phases will address situations where stockouts prevent sales from reflecting true demand.

Public retail data will be introduced for additional forecasting evaluation. Any assumed shelf lives, inventory states or cost parameters will be documented separately.

**Results from synthetic data or inventory simulations will not be presented as verified real-world financial savings.**

## Technology

- **Python:** Core implementation.
- **Python standard library:** Initial forecasting pipeline.
- **Planned additions:** Data processing libraries, forecasting and machine learning tools, optimisation solvers and Streamlit.

Dependencies will be introduced as the corresponding phases are implemented.

## Intended Outcome

The final system will allow a planner to inspect demand forecasts, understand uncertainty, adjust operational assumptions and compare replenishment decisions.

The project aims to demonstrate an end-to-end workflow covering:

- Time-series forecasting.
- Uncertainty estimation.
- Inventory simulation.
- Mathematical optimisation.
- Business-focused evaluation.
- Reproducible software development.

## Author

**Bodhisattwa Dhara**

Developed as a portfolio and research-oriented project connecting forecasting, optimisation and operational decision-making.

## Commit Phase 1

If you downloaded the Phase 1 ZIP, extract it and copy the **contents** of its
`FreshFlow/` folder into your existing repository checkout, including `.github/`
and `.gitignore`. Replace the existing README with this updated version.
Do not copy it as a nested `FreshFlow/FreshFlow/` directory.

If you do not have a local checkout yet:

```bash
git clone https://github.com/bodhi12496/FreshFlow.git
cd FreshFlow
```

After copying the files, run:

```bash
python3 -m unittest -v
python3 freshflow.py
git diff --check
git status --short
git add freshflow.py test_freshflow.py .gitignore .github/workflows/ci.yml README.md docs reports
git commit -m "Build Phase 1 reproducible forecasting benchmark"
git push origin main
```

No commit or push is performed by the Python pipeline.
