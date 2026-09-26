"""Direct multi-horizon boosting, feature ablations and paired forecast comparisons."""

import argparse
import hashlib
import json
import math
import platform
from collections import defaultdict
from datetime import date
from importlib.metadata import version
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from freshflow import MODELS, PRODUCTS, STORES, forecast, generate_data, summarize, validate_data, write_csv


FEATURES = (
    "store", "product", "horizon_day", "lag_1", "lag_7", "lag_14", "lag_28",
    "mean_7", "mean_28", "mean_56", "std_28", "weekday_mean_4",
    "weekday_sin", "weekday_cos", "year_sin", "year_cos", "time_index", "promotion",
)
BOOSTERS = ("gb_global", "gb_no_promotion", "gb_local")
ROOT = Path(__file__).resolve().parent


def load_protocol():
    return json.loads((ROOT / "phase2_protocol.json").read_text(encoding="utf-8"))


def features(history, target_date, horizon_day, key, promotion):
    """History ends at the forecast origin. Only target calendar/plan is future-known."""
    history = np.asarray(history, dtype=float)
    if history.ndim != 1 or len(history) < 56 or not np.isfinite(history).all() or (history < 0).any():
        raise ValueError("Features need at least 56 finite, nonnegative historical values")
    if type(horizon_day) is not int or horizon_day < 1 or promotion not in (0, 1):
        raise ValueError("Invalid horizon or promotion flag")
    store, product = key
    j = (horizon_day - 1) % 7
    weekday_angle = 2 * math.pi * target_date.weekday() / 7
    year_angle = 2 * math.pi * (target_date.timetuple().tm_yday - 1) / 365.25
    return [
        list(STORES).index(store), list(PRODUCTS).index(product), horizon_day,
        *[history[-lag] for lag in (1, 7, 14, 28)],
        *[float(history[-window:].mean()) for window in (7, 28, 56)],
        float(history[-28:].std()), float(history[-28 + j::7].mean()),
        math.sin(weekday_angle), math.cos(weekday_angle),
        math.sin(year_angle), math.cos(year_angle),
        (target_date - date(2023, 1, 1)).days, promotion,
    ]


def panel(rows):
    dates, series = validate_data(rows)
    keys = sorted(series)
    promotions = {(r["store_id"], r["product_id"], r["date"]): r["promotion"] for r in rows}
    demand = np.asarray([series[key] for key in keys], dtype=float)
    plans = np.asarray([[promotions[(*key, day.isoformat())] for day in dates] for key in keys])
    return dates, keys, demand, plans


def samples(dates, keys, demand, plans, horizon, stride):
    """Cache examples; every fit MUST filter target indices to before its cutoff."""
    x, y, origins, targets, series_ids = [], [], [], [], []
    for series_id, key in enumerate(keys):
        # ponytail: weekly origins reduce training rows but cover one origin weekday;
        # use stride=1 in a new held-out experiment to test daily-origin coverage.
        for origin in range(56, len(dates) - horizon + 1, stride):
            history = demand[series_id, :origin]
            for h in range(1, horizon + 1):
                target = origin + h - 1
                x.append(features(history, dates[target], h, key, int(plans[series_id, target])))
                y.append(demand[series_id, target])
                origins.append(origin)
                targets.append(target)
                series_ids.append(series_id)
    return tuple(np.asarray(v) for v in (x, y, origins, targets, series_ids))


def predict_at_origin(dates, keys, demand, plans, origin, config, cached):
    """Fit from observable labels and predict all horizon days from one fixed origin."""
    horizon = config["horizon"]
    x, y, train_origins, targets, series_ids = cached
    train = (targets < origin) & (train_origins < origin)
    if not train.any():
        raise ValueError("No training examples before the forecast origin")
    query = np.asarray([
        features(demand[s, :origin], dates[origin + h - 1], h, key, int(plans[s, origin + h - 1]))
        for s, key in enumerate(keys) for h in range(1, horizon + 1)
    ])
    result = {}
    # Limit native threads to keep this small benchmark reproducible and laptop-friendly.
    with threadpool_limits(limits=1):
        for name in BOOSTERS:
            columns = list(range(len(FEATURES) - (name == "gb_no_promotion")))
            prediction = np.empty(len(query))
            groups = range(len(keys)) if name == "gb_local" else (None,)
            for series_id in groups:
                subset = train if series_id is None else train & (series_ids == series_id)
                query_rows = slice(None) if series_id is None else slice(series_id * horizon, (series_id + 1) * horizon)
                model = HistGradientBoostingRegressor(categorical_features=[0, 1], **config["model"])
                model.fit(x[subset][:, columns], y[subset])
                prediction[query_rows] = model.predict(query[query_rows][:, columns])
            result[name] = np.maximum(prediction, 0).reshape(len(keys), horizon)
    audit = {"training_rows": int(train.sum()),
             "max_training_target": dates[int(targets[train].max())].isoformat(),
             "last_observed_date": dates[origin - 1].isoformat()}
    return result, audit


def select_model(predictions, candidates):
    scores = summarize([r for r in predictions if r["split"] == "validation" and r["model"] in candidates], ("model",))
    if not scores:
        raise ValueError("Model selection requires validation predictions")
    return min(scores, key=lambda r: (r["mae"], r["model"]))["model"]


def validate_config(config):
    positive = ("days", "horizon", "validation_folds", "test_folds", "training_stride",
                "bootstrap_samples", "bootstrap_block_days")
    if any(type(config[k]) is not int or config[k] < 1 for k in positive):
        raise ValueError("Days, horizons, folds, stride and bootstrap settings must be positive integers")
    if type(config["seed"]) is not int or config["seed"] < 0:
        raise ValueError("Seed must be a nonnegative integer")
    first = config["days"] - (config["validation_folds"] + config["test_folds"]) * config["horizon"]
    if first < 56 + config["horizon"]:
        raise ValueError("Not enough initial history for a complete supervised horizon")
    if config["model"]["early_stopping"] is not False:
        raise ValueError("Random-split early stopping is disabled by the temporal protocol")
    return first


def backtest(rows, config, verbose=False):
    first = validate_config(config)
    dates, keys, demand, plans = panel(rows)
    if len(dates) != config["days"]:
        raise ValueError("Data length does not match protocol")
    horizon = config["horizon"]
    cached = samples(dates, keys, demand, plans, horizon, config["training_stride"])
    predictions, audits = [], []
    selected = baseline = None
    total = config["validation_folds"] + config["test_folds"]
    for fold in range(total):
        split = "validation" if fold < config["validation_folds"] else "test"
        if fold == config["validation_folds"]:
            # Freeze both choices BEFORE forecasting or inspecting the test period.
            selected = select_model(predictions, (*MODELS, *BOOSTERS))
            baseline = select_model(predictions, MODELS)
        origin = first + fold * horizon
        if verbose:
            print(f"{split} fold {fold + 1}/{total}: cutoff {dates[origin - 1]}", flush=True)
        estimates, audit = predict_at_origin(dates, keys, demand, plans, origin, config, cached)
        audits.append({"split": split, "fold": fold + 1, **audit})
        for s, key in enumerate(keys):
            history = demand[s, :origin]
            scale = float(np.abs(history[7:] - history[:-7]).mean())
            forecasts = forecast(history.tolist(), horizon)
            forecasts.update({name: values[s] for name, values in estimates.items()})
            for model, values in forecasts.items():
                for h, value in enumerate(values):
                    predictions.append({
                        "split": split, "fold": fold + 1, "origin": str(dates[origin - 1]),
                        "date": str(dates[origin + h]), "horizon_day": h + 1,
                        "store_id": key[0], "product_id": key[1],
                        "promotion": int(plans[s, origin + h]), "model": model,
                        "actual": int(demand[s, origin + h]), "prediction": float(value),
                        "mase_scale": scale,
                    })
    return predictions, audits, selected, baseline


def block_interval(differences, block_days, repetitions, seed):
    """Circular moving-block bootstrap of daily paired mean absolute-error differences."""
    values = np.asarray(differences, dtype=float)
    if (values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all()
            or block_days < 1 or repetitions < 1):
        raise ValueError("Need finite daily differences and positive bootstrap settings")
    if len(values) < 2 * block_days:
        return None, None  # Too few blocks for even an exploratory interval.
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(values), size=(repetitions, math.ceil(len(values) / block_days)))
    indices = ((starts[..., None] + np.arange(block_days)) % len(values)).reshape(repetitions, -1)
    means = values[indices[:, :len(values)]].mean(axis=1)
    return tuple(float(v) for v in np.quantile(means, [0.025, 0.975]))


def compare(predictions, candidate, reference, split, config):
    def indexed(model):
        result = {}
        for row in predictions:
            if row["model"] != model or row["split"] != split:
                continue
            key = tuple(row[k] for k in ("origin", "date", "horizon_day", "store_id", "product_id"))
            if key in result:
                raise ValueError("Duplicate prediction in paired comparison")
            result[key] = row
        return result
    a, b = indexed(candidate), indexed(reference)
    if not a or a.keys() != b.keys():
        raise ValueError("Paired comparison requires identical forecast cases")
    daily = defaultdict(list)
    for key, row in a.items():
        other = b[key]
        if row["actual"] != other["actual"]:
            raise ValueError("Paired actual demand differs")
        daily[row["date"]].append(abs(row["prediction"] - row["actual"])
                                  - abs(other["prediction"] - other["actual"]))
    dates = [date.fromisoformat(day) for day in sorted(daily)]
    if len({len(v) for v in daily.values()}) != 1 or any((b - a).days != 1 for a, b in zip(dates, dates[1:])):
        raise ValueError("Bootstrap expects a balanced, consecutive daily panel")
    differences = [float(np.mean(daily[str(day)])) for day in dates]
    lo, hi = block_interval(differences, config["bootstrap_block_days"], config["bootstrap_samples"], config["seed"])
    return {"split": split, "candidate": candidate, "reference": reference,
            "mae_difference": float(np.mean(differences)), "ci95_low": lo, "ci95_high": hi,
            "days": len(differences), "series_per_day": len(next(iter(daily.values()))),
            "block_days": config["bootstrap_block_days"], "bootstrap_samples": config["bootstrap_samples"]}


def segment_comparisons(predictions, selected, baseline):
    output = []
    for dimension in ("store_id", "product_id", "promotion", "horizon_day"):
        scores = summarize(predictions, ("split", "model", dimension))
        lookup = {(r["split"], r["model"], r[dimension]): r for r in scores}
        for row in scores:
            if row["model"] != selected:
                continue
            reference = lookup[(row["split"], baseline, row[dimension])]
            base = reference["mae"]
            output.append({"split": row["split"], "dimension": dimension, "segment": row[dimension],
                           "selected_model": selected, "baseline": baseline, "n": row["n"],
                           "model_mae": row["mae"], "baseline_mae": base,
                           "improvement_pct": 100 * (base - row["mae"]) / base if base else None})
    return output


def report(scores, comparisons, segments, selected, baseline, config, audits, smoke):
    def fmt(value):
        return "N/A" if value is None else f"{value:.3f}"
    test = {r["model"]: r for r in scores if r["split"] == "test"}
    gain = 100 * (test[baseline]["mae"] - test[selected]["mae"]) / test[baseline]["mae"] if test[baseline]["mae"] else None
    lines = ["# Phase 2: strong forecasting", "",
             "**SMOKE CHECK ONLY — not a portfolio benchmark.**" if smoke else "**Synthetic benchmark — no real-world savings or inventory decisions measured.**", "",
             f"Seed **{config['seed']}**, **{config['days']} days**, **18 series**, **{config['horizon']}-day forecasts**.",
             f"Validation: **{config['validation_folds']} folds**; final rolling test: **{config['test_folds']} folds**.",
             f"First validation cutoff: **{audits[0]['last_observed_date']}**; "
             f"first test cutoff: **{audits[config['validation_folds']]['last_observed_date']}**.", "",
             f"Frozen validation selections: model **`{selected}`**, baseline **`{baseline}`**.",
             f"Final-test MAE improvement over that baseline: **{fmt(gain)}%**.", "",
             "## All models", "", "| Split | Model | MAE | WAPE (%) | MASE | Bias (units) |",
             "|---|---|---:|---:|---:|---:|"]
    for split in ("validation", "test"):
        for row in sorted((r for r in scores if r["split"] == split), key=lambda r: r["mae"]):
            lines.append(f"| {split} | {row['model']} | " + " | ".join(fmt(row[k]) for k in ("mae", "wape_pct", "mase", "bias_units")) + " |")
    lines += ["", "## Paired comparisons on the final test", "",
              "Negative differences favour the candidate. Intervals are exploratory 95% circular "
              "moving-block bootstrap intervals over paired daily errors, keeping all stores/products together.", "",
              "| Candidate | Reference | MAE difference | 95% interval |",
              "|---|---|---:|---|"]
    for row in comparisons:
        if row["split"] == "test":
            lines.append(f"| {row['candidate']} | {row['reference']} | {fmt(row['mae_difference'])} | "
                         f"[{fmt(row['ci95_low'])}, {fmt(row['ci95_high'])}] |")
    lines += ["", f"Block length: {config['bootstrap_block_days']} days; {config['bootstrap_samples']} resamples. "
              "These are intervals for average error differences, not demand forecast intervals. "
              "No multiple-comparison correction; no claim of universal statistical superiority.", "",
              "## Where the validation-selected model helps or hurts", "",
              "Positive improvement means lower MAE than the validation-selected baseline.", "",
              "| Dimension | Segment | Cases | Model MAE | Baseline MAE | Improvement (%) |",
              "|---|---|---:|---:|---:|---:|"]
    for row in segments:
        if row["split"] == "test" and row["dimension"] != "horizon_day":
            lines.append(f"| {row['dimension']} | {row['segment']} | {row['n']} | {fmt(row['model_mae'])} | "
                         f"{fmt(row['baseline_mae'])} | {fmt(row['improvement_pct'])} |")
    lines += ["", "## Interpretation and limitations", "",
              "- `gb_global`: one model across all series and horizons, with store/product categories.",
              "- `gb_no_promotion`: the same global approach with the promotion flag removed.",
              "- `gb_local`: one model per store/product, with the same features and hyperparameters.",
              "- Promotion information is assumed scheduled and known 14 days ahead; the ablation measures predictive value, not causal uplift.",
              "- Model choices and hyperparameters stay fixed during test; refits may use earlier test days once observed.",
              "- One synthetic seed, related temporal observations and a simple demand generator limit generalisation.",
              "- Baselines, zero-denominator metric definitions and Phase 1 remain available unchanged.",
              "- Full series, promotion, horizon and fold diagnostics plus training-cutoff audits accompany this report.", ""]
    return "\n".join(lines)


def plot_results(output, scores, segments, selected):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = sorted((r for r in scores if r["split"] == "test"), key=lambda r: r["mae"])
    products = [r for r in segments if r["split"] == "test" and r["dimension"] == "product_id"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    fig.suptitle("FreshFlow · Phase 2 | synthetic final-test results", fontsize=15, fontweight="bold")
    axes[0].barh([r["model"] for r in rows], [r["mae"] for r in rows],
                 color=["#087f8c" if r["model"] == selected else "#9baabd" for r in rows])
    axes[0].invert_yaxis()
    axes[0].set(xlabel="MAE (units; lower is better)", title="All models on identical forecast cases")
    values = [r["improvement_pct"] if r["improvement_pct"] is not None else 0 for r in products]
    axes[1].barh([r["segment"] for r in products], values,
                 color=["#087f8c" if value >= 0 else "#c34a36" for value in values])
    axes[1].axvline(0, color="#334155", linewidth=1)
    axes[1].set(xlabel="MAE reduction vs validation-selected baseline (%)",
                title=f"Product results · {selected}")
    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="x", alpha=0.15)
        axis.set_axisbelow(True)
    fig.savefig(output / "comparison.png", dpi=160)
    plt.close(fig)


def run(output, smoke=False):
    config = load_protocol()
    if smoke:
        config.update(days=168, validation_folds=2, test_folds=2, bootstrap_samples=100)
        config["model"]["max_iter"] = 10
    validate_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Save the declared experiment before generating data or fitting any model.
    (output / "protocol.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    rows = generate_data(seed=config["seed"], days=config["days"])
    predictions, audits, selected, baseline = backtest(rows, config, verbose=True)
    scores = summarize(predictions, ("split", "model"))
    comparisons = [compare(predictions, model, baseline, split, config)
                   for split in ("validation", "test") for model in (*MODELS, *BOOSTERS) if model != baseline]
    comparisons += [compare(predictions, "gb_global", reference, split, config)
                    for split in ("validation", "test") for reference in ("gb_no_promotion", "gb_local")]
    segments = segment_comparisons(predictions, selected, baseline)
    artifacts = {"demand.csv": rows, "predictions.csv": predictions, "metrics.csv": scores,
                 "paired_comparisons.csv": comparisons, "segment_comparisons.csv": segments,
                 "training_audit.csv": audits}
    for name, dimensions in {"series": ("store_id", "product_id"), "store": ("store_id",),
                             "product": ("product_id",), "promotion": ("promotion",),
                             "horizon": ("horizon_day",), "fold": ("fold",)}.items():
        artifacts[f"metrics_by_{name}.csv"] = summarize(predictions, ("split", "model", *dimensions))
    for name, data in artifacts.items():
        write_csv(output / name, data)
    text = report(scores, comparisons, segments, selected, baseline, config, audits, smoke)
    (output / "report.md").write_text(text, encoding="utf-8")
    plot_results(output, scores, segments, selected)
    files = [*artifacts, "protocol.json", "report.md", "comparison.png"]
    manifest = {
        "phase": 2, "smoke": smoke, "python": platform.python_version(),
        "versions": {name: version(name) for name in ("numpy", "scipy", "scikit-learn", "matplotlib", "joblib", "threadpoolctl")},
        "config": config, "selected_model": selected, "selected_baseline": baseline,
        "selection_metric": "validation_mae", "features": FEATURES,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in ("freshflow.py", "phase2.py", "phase2_protocol.json", "requirements.txt")},
        "sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in files},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(text)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Generated files are overwritten here")
    parser.add_argument("--smoke", action="store_true", help="Small integration check; not a portfolio result")
    args = parser.parse_args()
    output = args.output or Path("artifacts/phase2-smoke" if args.smoke else "artifacts/phase2")
    try:
        run(output, args.smoke)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
