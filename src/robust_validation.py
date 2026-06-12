from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import RepeatedStratifiedKFold, train_test_split

from bootstrap_intervals import stratified_bootstrap_intervals
from data import load_data, preprocess_data
from data_integrity import DATA_PATH, validate_ai4i_dataset
from evaluation_metrics import classification_metrics
from experiment_run import create_experiment_run, record_current_process
from thesis_methodology_validation import (
    apply_calibrator,
    build_models,
    choose_threshold_by_validation_f1,
    fit_sigmoid,
)


def select_calibration_by_validation_brier(
    y_valid: pd.Series,
    valid_raw: np.ndarray,
) -> tuple[pd.DataFrame, str, dict[str, object | None]]:
    """Fit and select calibration using only the inner validation split."""
    calibrators: dict[str, object | None] = {
        "raw": None,
        "sigmoid": fit_sigmoid(valid_raw, y_valid),
        "isotonic": IsotonicRegression(out_of_bounds="clip").fit(valid_raw, y_valid),
    }
    rows = []
    for method, calibrator in calibrators.items():
        valid_probabilities = apply_calibrator(method, calibrator, valid_raw)
        rows.append(
            {
                "calibration_method": method,
                "validation_brier": round(float(brier_score_loss(y_valid, valid_probabilities)), 6),
            }
        )
    comparison = pd.DataFrame(rows)
    selected_method = str(comparison.sort_values(["validation_brier", "calibration_method"]).iloc[0]["calibration_method"])
    return comparison, selected_method, calibrators


def _fit_fold(
    X: pd.DataFrame,
    y: pd.Series,
    outer_train_idx: np.ndarray,
    outer_test_idx: np.ndarray,
    repeat: int,
    fold: int,
    fold_seed: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    inner_train_idx, valid_idx = train_test_split(
        outer_train_idx,
        test_size=0.25,
        stratify=y.iloc[outer_train_idx],
        random_state=fold_seed,
    )

    X_train = X.iloc[inner_train_idx]
    y_train = y.iloc[inner_train_idx]
    X_valid = X.iloc[valid_idx]
    y_valid = y.iloc[valid_idx]
    X_test = X.iloc[outer_test_idx]
    y_test = y.iloc[outer_test_idx]

    model = build_models(y_train, fold_seed)["xgboost"]
    model.fit(X_train, y_train)

    valid_raw = model.predict_proba(X_valid)[:, 1]
    test_raw = model.predict_proba(X_test)[:, 1]
    selected_threshold, _ = choose_threshold_by_validation_f1(y_valid, valid_raw)
    predictions = (test_raw >= selected_threshold).astype(int)
    test_metrics = classification_metrics(y_test, test_raw, predictions=predictions)
    validation_metrics = classification_metrics(y_valid, valid_raw, threshold=selected_threshold)

    calibration_rows, selected_method, calibrators = select_calibration_by_validation_brier(y_valid, valid_raw)
    selected_calibrator = calibrators[selected_method]
    test_calibrated = apply_calibrator(selected_method, selected_calibrator, test_raw)
    selected_calibration_row = calibration_rows[
        calibration_rows["calibration_method"] == selected_method
    ].iloc[0].to_dict()

    fold_row = {
        "repeat": repeat,
        "fold": fold,
        "fold_seed": fold_seed,
        "train_rows": int(len(y_train)),
        "validation_rows": int(len(y_valid)),
        "outer_test_rows": int(len(y_test)),
        "train_failures": int(y_train.sum()),
        "validation_failures": int(y_valid.sum()),
        "outer_test_failures": int(y_test.sum()),
        "selected_threshold": selected_threshold,
        "calibration_method": selected_method,
        "validation_f1_score": validation_metrics["f1_score"],
        "validation_precision": validation_metrics["precision"],
        "validation_recall": validation_metrics["recall"],
        "validation_pr_auc": validation_metrics["pr_auc"],
        "validation_roc_auc": validation_metrics["roc_auc"],
        "selected_calibration_validation_brier": selected_calibration_row["validation_brier"],
        "selected_calibration_outer_test_brier": round(float(brier_score_loss(y_test, test_calibrated)), 6),
        **{f"outer_test_{key}": value for key, value in test_metrics.items()},
    }
    prediction_rows = pd.DataFrame(
        {
            "source_row_index": X.index[outer_test_idx].astype(int),
            "repeat": repeat,
            "fold": fold,
            "fold_seed": fold_seed,
            "y_true": y_test.to_numpy(dtype=int),
            "raw_probability": test_raw,
            "calibrated_probability": test_calibrated,
            "selected_threshold": selected_threshold,
            "prediction": predictions,
        }
    )
    return fold_row, prediction_rows


def run_repeated_validation(
    repeats: int = 5,
    folds: int = 5,
    bootstrap_iterations: int = 2000,
    random_state: int = 20260612,
) -> dict[str, Any]:
    if repeats <= 0 or folds <= 1:
        raise ValueError("repeats must be positive and folds must be greater than 1.")

    raw_df = load_data(DATA_PATH)
    X, y = preprocess_data(raw_df)
    splitter = RepeatedStratifiedKFold(
        n_splits=folds,
        n_repeats=repeats,
        random_state=random_state,
    )

    fold_rows = []
    prediction_frames = []
    for split_number, (outer_train_idx, outer_test_idx) in enumerate(splitter.split(X, y), start=1):
        repeat = ((split_number - 1) // folds) + 1
        fold = ((split_number - 1) % folds) + 1
        fold_seed = random_state + split_number
        fold_row, prediction_rows = _fit_fold(
            X,
            y,
            outer_train_idx,
            outer_test_idx,
            repeat,
            fold,
            fold_seed,
        )
        fold_rows.append(fold_row)
        prediction_frames.append(prediction_rows)

    folds_df = pd.DataFrame(fold_rows)
    predictions_df = pd.concat(prediction_frames, ignore_index=True)
    aggregate_metrics = classification_metrics(
        predictions_df["y_true"],
        predictions_df["raw_probability"],
        predictions=predictions_df["prediction"],
    )
    fold_metric_columns = [
        "outer_test_precision",
        "outer_test_recall",
        "outer_test_f1_score",
        "outer_test_pr_auc",
        "outer_test_roc_auc",
        "selected_threshold",
    ]
    fold_metric_summary = (
        folds_df[fold_metric_columns]
        .agg(["mean", "std", "median", "min", "max"])
        .T.reset_index()
        .rename(columns={"index": "metric"})
        .round(6)
        .to_dict(orient="records")
    )
    bootstrap = stratified_bootstrap_intervals(
        predictions_df["y_true"],
        predictions_df["raw_probability"],
        predictions_df["prediction"],
        n_iterations=bootstrap_iterations,
        random_state=random_state,
    )

    return {
        "summary": {
            "scope": "AI4I repeated stratified outer validation",
            "repeats": repeats,
            "folds": folds,
            "outer_fold_count": int(repeats * folds),
            "random_state": random_state,
            "inner_selection": "Each outer train split is split again into fit and validation data; threshold and calibration are selected only on the inner validation split.",
            "fixed_baseline_note": "The accepted fixed 60:20:20 F1-score 0.7692 remains a separate representative split result.",
            "aggregate_oof_metrics": aggregate_metrics,
            "fold_metric_summary": fold_metric_summary,
            "bootstrap": bootstrap,
        },
        "folds": folds_df,
        "predictions": predictions_df,
    }


def write_robust_validation_files(
    run_id: str | None,
    repeats: int,
    folds: int,
    bootstrap_iterations: int,
    random_state: int,
) -> Path:
    run = create_experiment_run(run_id=run_id, prefix="robust-validation")
    record_current_process(run, phase="robust_validation")
    run.append_command(
        "robust_validation_parameters",
        [
            sys.executable,
            "src/robust_validation.py",
            "--repeats",
            str(repeats),
            "--folds",
            str(folds),
            "--bootstrap-iterations",
            str(bootstrap_iterations),
        ],
    )

    if not (run.run_dir / "data_manifest.json").exists():
        run.write_json("data_manifest.json", validate_ai4i_dataset())

    result = run_repeated_validation(
        repeats=repeats,
        folds=folds,
        bootstrap_iterations=bootstrap_iterations,
        random_state=random_state,
    )

    metrics_dir = run.run_dir / "metrics"
    predictions_dir = run.run_dir / "predictions"
    figures_dir = run.run_dir / "figures"
    reports_dir = run.run_dir / "reports"
    for directory in [metrics_dir, predictions_dir, figures_dir, reports_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    folds_path = metrics_dir / "robust_validation_fold_metrics.csv"
    predictions_path = predictions_dir / "robust_validation_oof_predictions.csv"
    summary_path = metrics_dir / "robust_validation_summary.json"
    bootstrap_path = metrics_dir / "robust_validation_bootstrap.csv"
    bootstrap_json_path = metrics_dir / "robust_validation_bootstrap.json"
    metric_figure_path = figures_dir / "robust_validation_metric_distribution.png"
    threshold_figure_path = figures_dir / "robust_validation_threshold_distribution.png"
    report_path = reports_dir / "robust_validation_report.md"

    result["folds"].to_csv(folds_path, index=False, encoding="utf-8-sig")
    result["predictions"].to_csv(predictions_path, index=False, encoding="utf-8-sig")
    summary_path.write_text(json.dumps(result["summary"], indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(result["summary"]["bootstrap"]["rows"]).to_csv(
        bootstrap_path,
        index=False,
        encoding="utf-8-sig",
    )
    bootstrap_json_path.write_text(
        json.dumps(result["summary"]["bootstrap"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    plot_metric_distribution(result["folds"], metric_figure_path)
    plot_threshold_distribution(result["folds"], threshold_figure_path)
    write_markdown_report(result["summary"], report_path)

    run.record_artifact(folds_path, "csv", "Per-fold repeated stratified validation metrics.")
    run.record_artifact(predictions_path, "csv", "Out-of-fold repeated validation predictions.")
    run.record_artifact(summary_path, "json", "Repeated validation aggregate summary.")
    run.record_artifact(bootstrap_path, "csv", "Stratified bootstrap confidence interval table.")
    run.record_artifact(bootstrap_json_path, "json", "Stratified bootstrap confidence interval details.")
    run.record_artifact(metric_figure_path, "png", "Outer-fold metric distribution figure.")
    run.record_artifact(threshold_figure_path, "png", "Validation-selected threshold distribution figure.")
    run.record_artifact(report_path, "markdown", "Reader-facing robust validation report.")
    run.update_status(
        "robust_validation_completed",
        {
            "outer_fold_count": int(repeats * folds),
            "bootstrap_iterations": int(bootstrap_iterations),
        },
    )
    print(f"RUN_ID={run.run_id}")
    print(f"RUN_DIR={run.run_dir}")
    return run.run_dir


def plot_metric_distribution(folds_df: pd.DataFrame, output_path: Path) -> None:
    metric_columns = {
        "Precision": "outer_test_precision",
        "Recall": "outer_test_recall",
        "F1": "outer_test_f1_score",
        "PR-AUC": "outer_test_pr_auc",
        "ROC-AUC": "outer_test_roc_auc",
    }
    plt.figure(figsize=(9.2, 5.4))
    data = [folds_df[column].astype(float).to_numpy() for column in metric_columns.values()]
    plt.boxplot(data, tick_labels=list(metric_columns.keys()), showmeans=True)
    plt.ylabel("Metric value")
    plt.title("Repeated Stratified Outer-Fold Metric Distribution")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def plot_threshold_distribution(folds_df: pd.DataFrame, output_path: Path) -> None:
    thresholds = folds_df["selected_threshold"].astype(float)
    plt.figure(figsize=(8.4, 5.0))
    plt.hist(thresholds, bins=np.arange(0.04, 0.98, 0.04), color="#1f77b4", edgecolor="white")
    plt.axvline(float(thresholds.mean()), color="#b3261e", linestyle="--", label=f"Mean {thresholds.mean():.2f}")
    plt.xlabel("Validation-selected raw probability threshold")
    plt.ylabel("Fold count")
    plt.title("Repeated Validation Threshold Distribution")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def write_markdown_report(summary: dict[str, Any], report_path: Path) -> None:
    metrics = summary["aggregate_oof_metrics"]
    bootstrap_rows = summary["bootstrap"]["rows"]
    lines = [
        "# Robust Validation Report",
        "",
        "This run keeps the accepted 0.86 fixed-test app policy separate from repeated validation.",
        "",
        "## Design",
        "",
        f"- Outer validation: {summary['folds']} folds x {summary['repeats']} repeats = {summary['outer_fold_count']} evaluations",
        "- Threshold and calibration selection: inner validation split only",
        "- Outer fold labels: used only for final fold evaluation",
        "- Hyperparameters: current baseline XGBoost settings reused",
        "",
        "## Aggregate Out-of-Fold Metrics",
        "",
        f"- Precision: {metrics['precision']}",
        f"- Recall: {metrics['recall']}",
        f"- F1-score: {metrics['f1_score']}",
        f"- PR-AUC: {metrics['pr_auc']}",
        f"- ROC-AUC: {metrics['roc_auc']}",
        "",
        "## Bootstrap 95% Confidence Intervals",
        "",
        "| Metric | Mean | Std | Median | Min | Max | 95% lower | 95% upper |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in bootstrap_rows:
        lines.append(
            "| {metric} | {mean:.6f} | {std:.6f} | {median:.6f} | {min:.6f} | {max:.6f} | {lower_95:.6f} | {upper_95:.6f} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "This result is still AI4I public-data internal repeated validation. It is not field deployment, real-time lead-time proof, or company-data performance proof.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated stratified validation and bootstrap CIs.")
    parser.add_argument("--run-id", default=None, help="Experiment run id. A timestamped id is generated if omitted.")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--random-state", type=int, default=20260612)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_robust_validation_files(
        run_id=args.run_id,
        repeats=args.repeats,
        folds=args.folds,
        bootstrap_iterations=args.bootstrap_iterations,
        random_state=args.random_state,
    )


if __name__ == "__main__":
    main()
