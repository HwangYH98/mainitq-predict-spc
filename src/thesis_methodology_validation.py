from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from data import TARGET_COLUMN, load_data, preprocess_data
from final_policy import final_threshold_summary


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
LOCK_PATH = PROJECT_ROOT / "requirements-lock.txt"
EXISTING_POLICY_PATH = OUTPUT_DIR / "operating_policy_thresholds.json"
SEEDS = [21, 42, 77, 100, 2026]
THRESHOLD_GRID = np.round(np.arange(0.05, 0.951, 0.01), 2)


@dataclass(frozen=True)
class SplitData:
    X_train: pd.DataFrame
    X_valid: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_valid: pd.Series
    y_test: pd.Series


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_60_20_20(X: pd.DataFrame, y: pd.Series, seed: int) -> SplitData:
    """Create fixed train, validation, and test splits."""
    X_train_valid, X_test, y_train_valid, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        stratify=y,
        random_state=seed,
    )
    X_train, X_valid, y_train, y_valid = train_test_split(
        X_train_valid,
        y_train_valid,
        test_size=0.25,
        stratify=y_train_valid,
        random_state=seed,
    )
    return SplitData(X_train, X_valid, X_test, y_train, y_valid, y_test)


def build_models(y_train: pd.Series, seed: int) -> dict[str, object]:
    positive_count = int(y_train.sum())
    negative_count = int(len(y_train) - positive_count)
    scale_pos_weight = negative_count / positive_count if positive_count else 1.0
    return {
        "logistic_regression": Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=seed,
                        solver="liblinear",
                    ),
                ),
            ]
        ),
        "xgboost": XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=seed,
            scale_pos_weight=scale_pos_weight,
        ),
    }


def metrics_at_threshold(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, float | int]:
    predictions = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 2),
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, predictions, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 4),
        "pr_auc": round(float(average_precision_score(y_true, probabilities)), 4),
        "brier_score": round(float(brier_score_loss(y_true, probabilities)), 6),
        "alert_count": int(fp + tp),
        "false_alarm_count": int(fp),
        "missed_failure_count": int(fn),
        "true_positive_count": int(tp),
        "true_negative_count": int(tn),
    }


def threshold_grid_metrics(y_true: pd.Series, probabilities: np.ndarray) -> pd.DataFrame:
    rows = [metrics_at_threshold(y_true, probabilities, float(threshold)) for threshold in THRESHOLD_GRID]
    return pd.DataFrame(rows)


def choose_threshold_by_validation_f1(y_true: pd.Series, probabilities: np.ndarray) -> tuple[float, pd.DataFrame]:
    grid = threshold_grid_metrics(y_true, probabilities)
    selected = grid.sort_values(["f1_score", "recall", "precision"], ascending=[False, False, False]).iloc[0]
    return float(selected["threshold"]), grid


def fit_sigmoid(raw_probabilities: np.ndarray, y_true: pd.Series) -> LogisticRegression:
    calibrator = LogisticRegression(solver="lbfgs")
    calibrator.fit(raw_probabilities.reshape(-1, 1), y_true)
    return calibrator


def apply_calibrator(method: str, calibrator: object | None, probabilities: np.ndarray) -> np.ndarray:
    if method == "raw":
        return probabilities
    if isinstance(calibrator, LogisticRegression):
        return calibrator.predict_proba(probabilities.reshape(-1, 1))[:, 1]
    if isinstance(calibrator, IsotonicRegression):
        return calibrator.predict(probabilities)
    raise ValueError(f"Unsupported calibration method: {method}")


def calibration_comparison(
    y_valid: pd.Series,
    valid_raw: np.ndarray,
    y_test: pd.Series,
    test_raw: np.ndarray,
) -> tuple[pd.DataFrame, str, dict[str, object | None], dict[str, np.ndarray]]:
    calibrators: dict[str, object | None] = {
        "raw": None,
        "sigmoid": fit_sigmoid(valid_raw, y_valid),
        "isotonic": IsotonicRegression(out_of_bounds="clip").fit(valid_raw, y_valid),
    }
    rows = []
    calibrated_test_probabilities: dict[str, np.ndarray] = {}
    for method, calibrator in calibrators.items():
        valid_probabilities = apply_calibrator(method, calibrator, valid_raw)
        test_probabilities = apply_calibrator(method, calibrator, test_raw)
        calibrated_test_probabilities[method] = test_probabilities
        rows.append(
            {
                "calibration_method": method,
                "validation_brier": round(float(brier_score_loss(y_valid, valid_probabilities)), 6),
                "test_brier": round(float(brier_score_loss(y_test, test_probabilities)), 6),
            }
        )
    comparison = pd.DataFrame(rows)
    selected_method = str(comparison.sort_values(["validation_brier", "calibration_method"]).iloc[0]["calibration_method"])
    return comparison, selected_method, calibrators, calibrated_test_probabilities


def choose_operating_policies(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, dict[str, float | int]]:
    grid = threshold_grid_metrics(y_true, probabilities)
    balanced = grid.sort_values(["f1_score", "recall"], ascending=[False, False]).iloc[0]
    precision_candidates = grid[grid["precision"] >= 0.8]
    precision_first = (
        precision_candidates.sort_values(["recall", "f1_score"], ascending=[False, False]).iloc[0]
        if not precision_candidates.empty
        else grid.sort_values(["precision", "f1_score"], ascending=[False, False]).iloc[0]
    )
    recall_candidates = grid[grid["recall"] >= 0.85]
    recall_first = (
        recall_candidates.sort_values(["precision", "f1_score"], ascending=[False, False]).iloc[0]
        if not recall_candidates.empty
        else grid.sort_values(["recall", "f1_score"], ascending=[False, False]).iloc[0]
    )
    return {
        "balanced": balanced.to_dict(),
        "precision_first": precision_first.to_dict(),
        "recall_first": recall_first.to_dict(),
    }


def plot_threshold_curve(grid: pd.DataFrame, selected_threshold: float, output_path: Path) -> None:
    plt.figure(figsize=(8.2, 5.2))
    plt.plot(grid["threshold"], grid["precision"], label="Validation precision", linewidth=2)
    plt.plot(grid["threshold"], grid["recall"], label="Validation recall", linewidth=2)
    plt.plot(grid["threshold"], grid["f1_score"], label="Validation F1", linewidth=2)
    plt.axvline(selected_threshold, color="#b3261e", linestyle="--", label=f"Selected {selected_threshold:.2f}")
    plt.xlabel("Raw probability threshold")
    plt.ylabel("Score")
    plt.title("Validation-Set Threshold Selection")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=220)
    plt.close()


def plot_calibration_curves(
    y_test: pd.Series,
    traces: dict[str, np.ndarray],
    selected_method: str,
    output_path: Path,
) -> None:
    plt.figure(figsize=(7.2, 5.6))
    plt.plot([0, 1], [0, 1], linestyle="--", color="#666666", label="Perfect calibration")
    for method, probabilities in traces.items():
        fraction, mean_predicted = calibration_curve(y_test, probabilities, n_bins=8, strategy="quantile")
        label = f"{method} (selected)" if method == selected_method else method
        plt.plot(mean_predicted, fraction, marker="o", label=label)
    plt.xlabel("Mean predicted probability")
    plt.ylabel("Observed failure fraction")
    plt.title("Test Calibration After Validation-Set Method Selection")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=220)
    plt.close()


def write_requirements_lock() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    LOCK_PATH.write_text(result.stdout, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    """Render a compact GitHub-style table without optional dependencies."""
    if df.empty:
        return "_No rows._"
    table = df.copy()
    table = table.fillna("")
    columns = [str(column) for column in table.columns]
    rows = []
    rows.append("| " + " | ".join(columns) + " |")
    rows.append("| " + " | ".join("---" for _ in columns) + " |")
    for _, row in table.iterrows():
        values = [str(row[column]).replace("\n", " ") for column in table.columns]
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def current_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "not_available"


def write_summary(
    payload: dict,
    model_rows: pd.DataFrame,
    calibration_rows: pd.DataFrame,
    policy_rows: pd.DataFrame,
    sensitivity_summary: pd.DataFrame,
) -> None:
    selected = payload["xgboost_raw_threshold_selection"]
    selected_method = payload["calibration"]["selected_method"]
    lines = [
        "# Thesis Methodology Validation Summary",
        "",
        "## 1. Train-Validation-Test Separation",
        "",
        f"- Data: AI4I 10,000 rows / target: `{TARGET_COLUMN}`",
        f"- Split: train {payload['split']['train_rows']}, validation {payload['split']['validation_rows']}, fixed test {payload['split']['test_rows']}",
        f"- Validation-selected raw XGBoost threshold: `{selected['selected_threshold']:.2f}`",
        f"- Fixed-test F1-score: `{selected['test_metrics']['f1_score']:.4f}`",
        f"- Fixed-test PR-AUC: `{selected['test_metrics']['pr_auc']:.4f}`",
        "",
        "## 2. Model Metrics",
        "",
        markdown_table(model_rows),
        "",
        "## 3. Calibration Method Selection",
        "",
        f"- Method selected by validation Brier score: `{selected_method}`",
        "",
        markdown_table(calibration_rows),
        "",
        "## 4. Calibrated Probability Reference Policies",
        "",
        markdown_table(policy_rows),
        "",
        "## 4-1. Final App Decision Policy",
        "",
        "- Desktop and Streamlit classify High Risk with raw probability threshold `0.86`.",
        "- Calibrated thresholds are reference trade-off policies, not the default app decision threshold.",
        "- Legacy `0.87` is preserved only as the old 80:20 exploratory same-holdout result.",
        "",
        "## 5. Repeated Split Sensitivity",
        "",
        markdown_table(sensitivity_summary),
        "",
        "## Manuscript Insert Sentences",
        "",
        (
            "The AI4I dataset was stratified into 60% training, 20% validation, and 20% fixed test sets. "
            "The model was fitted only on the training set, and both the raw-probability threshold and calibration method were selected on the validation set. "
            "The selected threshold and calibration method were then fixed before final evaluation on the fixed test set."
        ),
        "",
        (
            f"The validation-selected XGBoost raw-probability threshold was {selected['selected_threshold']:.2f}. "
            f"On the fixed test set separated from validation, F1-score was {selected['test_metrics']['f1_score']:.4f}, "
            f"PR-AUC was {selected['test_metrics']['pr_auc']:.4f}, and ROC-AUC was {selected['test_metrics']['roc_auc']:.4f}."
        ),
        "",
        (
            f"The calibration method was selected by validation-set Brier score, and the selected method was `{selected_method}`. "
            "The fixed test set was not used for calibration-method selection."
        ),
        "",
    ]
    (OUTPUT_DIR / "thesis_methodology_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_once(seed: int = 42, save_artifacts: bool = True) -> dict:
    raw_df = load_data(DATA_PATH)
    X, y = preprocess_data(raw_df)
    split = split_60_20_20(X, y, seed)
    models = build_models(split.y_train, seed)
    model_rows = []
    fitted_models = {}

    for model_name, model in models.items():
        model.fit(split.X_train, split.y_train)
        fitted_models[model_name] = model
        test_probabilities = model.predict_proba(split.X_test)[:, 1]
        row = {
            "model": model_name,
            "probability_type": "raw",
            **metrics_at_threshold(split.y_test, test_probabilities, 0.5),
        }
        model_rows.append(row)

    xgb = fitted_models["xgboost"]
    valid_raw = xgb.predict_proba(split.X_valid)[:, 1]
    test_raw = xgb.predict_proba(split.X_test)[:, 1]
    selected_threshold, threshold_grid = choose_threshold_by_validation_f1(split.y_valid, valid_raw)
    validation_selected_metrics = metrics_at_threshold(split.y_valid, valid_raw, selected_threshold)
    test_selected_metrics = metrics_at_threshold(split.y_test, test_raw, selected_threshold)
    model_rows.append(
        {
            "model": "xgboost",
            "probability_type": "raw_validation_selected_threshold",
            **test_selected_metrics,
        }
    )

    calibration_rows, selected_method, calibrators, calibrated_test_traces = calibration_comparison(
        split.y_valid,
        valid_raw,
        split.y_test,
        test_raw,
    )
    selected_calibrator = calibrators[selected_method]
    valid_calibrated = apply_calibrator(selected_method, selected_calibrator, valid_raw)
    test_calibrated = apply_calibrator(selected_method, selected_calibrator, test_raw)
    policies = choose_operating_policies(split.y_valid, valid_calibrated)
    policy_rows = []
    for policy_id, validation_policy in policies.items():
        threshold = float(validation_policy["threshold"])
        test_policy = metrics_at_threshold(split.y_test, test_calibrated, threshold)
        policy_rows.append(
            {
                "policy_id": policy_id,
                "calibration_method": selected_method,
                "validation_threshold": threshold,
                "validation_f1": round(float(validation_policy["f1_score"]), 4),
                "validation_precision": round(float(validation_policy["precision"]), 4),
                "validation_recall": round(float(validation_policy["recall"]), 4),
                "test_precision": test_policy["precision"],
                "test_recall": test_policy["recall"],
                "test_f1_score": test_policy["f1_score"],
                "test_false_alarm_count": test_policy["false_alarm_count"],
                "test_missed_failure_count": test_policy["missed_failure_count"],
            }
        )

    payload = {
        "scope": "thesis methodology validation with train/validation/test separation",
        "dataset_path": str(DATA_PATH.relative_to(PROJECT_ROOT)),
        "dataset_sha256": sha256_file(DATA_PATH),
        "target_column": TARGET_COLUMN,
        "seed": seed,
        "split": {
            "train_rows": int(len(split.y_train)),
            "validation_rows": int(len(split.y_valid)),
            "test_rows": int(len(split.y_test)),
            "train_failures": int(split.y_train.sum()),
            "validation_failures": int(split.y_valid.sum()),
            "test_failures": int(split.y_test.sum()),
        },
        "xgboost_raw_threshold_selection": {
            "selection_basis": "validation F1-score over thresholds 0.05..0.95",
            "selected_threshold": selected_threshold,
            "validation_metrics": validation_selected_metrics,
            "test_metrics": test_selected_metrics,
        },
        "calibration": {
            "selection_basis": "validation Brier score",
            "selected_method": selected_method,
            "rows": calibration_rows.to_dict(orient="records"),
        },
        "reproducibility": {
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "git_commit": current_git_commit(),
            "random_seeds": SEEDS,
        },
    }

    if save_artifacts:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        model_df = pd.DataFrame(model_rows)
        policy_df = pd.DataFrame(policy_rows)
        model_df.to_csv(OUTPUT_DIR / "thesis_60_20_20_metrics.csv", index=False, encoding="utf-8-sig")
        threshold_grid.to_csv(OUTPUT_DIR / "thesis_validation_threshold_grid.csv", index=False, encoding="utf-8-sig")
        calibration_rows.to_csv(OUTPUT_DIR / "thesis_calibration_comparison.csv", index=False, encoding="utf-8-sig")
        policy_df.to_csv(OUTPUT_DIR / "thesis_operating_policy_thresholds.csv", index=False, encoding="utf-8-sig")
        (OUTPUT_DIR / "thesis_methodology_metrics.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        default_metrics = threshold_grid.loc[
            threshold_grid["threshold"] == 0.50,
            ["precision", "recall", "f1_score"],
        ].iloc[0].to_dict()
        (OUTPUT_DIR / "threshold_summary.json").write_text(
            json.dumps(final_threshold_summary(default_metrics), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        plot_threshold_curve(threshold_grid, selected_threshold, OUTPUT_DIR / "thesis_validation_threshold_curve.png")
        plot_calibration_curves(
            split.y_test,
            calibrated_test_traces,
            selected_method,
            OUTPUT_DIR / "thesis_calibration_curve_independent_test.png",
        )
    return {
        "payload": payload,
        "model_rows": pd.DataFrame(model_rows),
        "calibration_rows": calibration_rows,
        "policy_rows": pd.DataFrame(policy_rows),
    }


def run_seed_sensitivity() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = load_data(DATA_PATH)
    X, y = preprocess_data(raw_df)
    rows = []
    for seed in SEEDS:
        split = split_60_20_20(X, y, seed)
        model = build_models(split.y_train, seed)["xgboost"]
        model.fit(split.X_train, split.y_train)
        valid_raw = model.predict_proba(split.X_valid)[:, 1]
        test_raw = model.predict_proba(split.X_test)[:, 1]
        selected_threshold, _ = choose_threshold_by_validation_f1(split.y_valid, valid_raw)
        rows.append(
            {
                "seed": seed,
                "selected_threshold": selected_threshold,
                **metrics_at_threshold(split.y_test, test_raw, selected_threshold),
            }
        )
    details = pd.DataFrame(rows)
    summary = (
        details[["pr_auc", "roc_auc", "f1_score"]]
        .agg(["mean", "std", "min", "max"])
        .T.reset_index()
        .rename(columns={"index": "metric"})
    )
    for column in ["mean", "std", "min", "max"]:
        summary[column] = summary[column].round(4)
    return details, summary


def write_reproducibility_appendix(payload: dict, sensitivity_summary: pd.DataFrame) -> None:
    metadata = {
        "dataset_sha256": payload["dataset_sha256"],
        "git_commit": payload["reproducibility"]["git_commit"],
        "python": payload["reproducibility"]["python"],
        "platform": payload["reproducibility"]["platform"],
        "random_seeds": SEEDS,
        "commands": [
            ".\\.venv\\Scripts\\python.exe src\\thesis_methodology_validation.py",
            ".\\.venv\\Scripts\\python.exe -m pytest -q tests\\test_thesis_methodology_validation.py",
        ],
        "gemini_model": "gemini-2.5-flash",
        "gemini_temperature": 0.2,
        "secret_policy": "API keys are session-only and are not written to files.",
    }
    (OUTPUT_DIR / "thesis_reproducibility_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    lines = [
        "# Reproducibility Appendix",
        "",
        "- Data file: `data/ai4i2020.csv`",
        f"- Data SHA-256: `{metadata['dataset_sha256']}`",
        f"- Git commit hash: `{metadata['git_commit']}`",
        f"- Python: `{metadata['python']}`",
        f"- OS/Platform: `{metadata['platform']}`",
        f"- Random seeds: `{', '.join(str(seed) for seed in SEEDS)}`",
        "- Package versions: `requirements-lock.txt`",
        "- API keys are session-only and are not written to files.",
        "",
        "## Commands",
        "",
        "```powershell",
        *metadata["commands"],
        "```",
        "",
        "## Repeated Split Sensitivity",
        "",
        markdown_table(sensitivity_summary),
        "",
        "Because only five seeds are used, the manuscript reports mean, standard deviation, minimum, and maximum instead of a 95% confidence interval.",
        "",
    ]
    (OUTPUT_DIR / "thesis_reproducibility_appendix.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_result = run_once(seed=42, save_artifacts=True)
    sensitivity_details, sensitivity_summary = run_seed_sensitivity()
    sensitivity_details.to_csv(OUTPUT_DIR / "thesis_seed_sensitivity.csv", index=False, encoding="utf-8-sig")
    sensitivity_summary.to_csv(OUTPUT_DIR / "thesis_seed_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    write_requirements_lock()
    write_reproducibility_appendix(run_result["payload"], sensitivity_summary)
    write_summary(
        run_result["payload"],
        run_result["model_rows"],
        run_result["calibration_rows"],
        run_result["policy_rows"],
        sensitivity_summary,
    )
    print("Thesis methodology validation finished.")
    print(f"Metrics: {OUTPUT_DIR / 'thesis_methodology_metrics.json'}")
    print(f"Summary: {OUTPUT_DIR / 'thesis_methodology_summary.md'}")
    print(f"Requirements lock: {LOCK_PATH}")


if __name__ == "__main__":
    main()
