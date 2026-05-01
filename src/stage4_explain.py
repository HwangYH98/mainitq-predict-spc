import json
from pathlib import Path

import matplotlib

# Save plots as image files without opening a GUI window.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import f1_score, precision_score, recall_score

from data import TARGET_COLUMN, prepare_train_test_data
from train_baseline import RANDOM_STATE, TEST_SIZE, build_models


def evaluate_thresholds(y_true: pd.Series, y_proba: np.ndarray) -> pd.DataFrame:
    """Compare precision, recall, and F1-score across many thresholds."""
    rows = []

    # 0.05 to 0.95 keeps the search simple and easy to explain in presentation.
    thresholds = np.round(np.arange(0.05, 0.951, 0.01), 2)

    for threshold in thresholds:
        y_pred = (y_proba >= threshold).astype(int)
        rows.append(
            {
                "threshold": float(threshold),
                "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
                "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
            }
        )

    return pd.DataFrame(rows)


def select_best_threshold(threshold_metrics: pd.DataFrame) -> dict:
    """Pick the threshold with best F1-score, then highest recall if tied."""
    sorted_metrics = threshold_metrics.sort_values(
        by=["f1_score", "recall"],
        ascending=[False, False],
    )
    return sorted_metrics.iloc[0].to_dict()


def save_threshold_plot(threshold_metrics: pd.DataFrame, best_threshold: float, output_path: Path) -> None:
    """Save a line plot showing how metrics change by threshold."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(9, 6))
    plt.plot(threshold_metrics["threshold"], threshold_metrics["precision"], label="Precision", linewidth=2)
    plt.plot(threshold_metrics["threshold"], threshold_metrics["recall"], label="Recall", linewidth=2)
    plt.plot(threshold_metrics["threshold"], threshold_metrics["f1_score"], label="F1-score", linewidth=2)
    plt.axvline(best_threshold, color="black", linestyle="--", label=f"Best threshold={best_threshold:.2f}")
    plt.xlabel("Threshold")
    plt.ylabel("Score")
    plt.title("XGBoost Threshold Tuning")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def calculate_shap_values(model, X_train: pd.DataFrame, X_test: pd.DataFrame) -> np.ndarray:
    """Calculate SHAP values for the trained XGBoost model."""
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)

    # Some SHAP/model combinations return a list for classification models.
    # For binary failure prediction, the positive class explanation is the one we need.
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    return np.asarray(shap_values)


def save_shap_plots(shap_values: np.ndarray, X_test: pd.DataFrame, output_dir: Path) -> None:
    """Save global SHAP plots for presentation."""
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.figure()
    shap.summary_plot(shap_values, X_test, show=False, max_display=10)
    plt.title("XGBoost SHAP Summary")
    plt.tight_layout()
    plt.savefig(output_dir / "shap_summary.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure()
    shap.summary_plot(shap_values, X_test, plot_type="bar", show=False, max_display=10)
    plt.title("XGBoost Mean Absolute SHAP Importance")
    plt.tight_layout()
    plt.savefig(output_dir / "shap_bar.png", dpi=300, bbox_inches="tight")
    plt.close()


def pick_explanation_case(
    raw_df: pd.DataFrame,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    y_proba: np.ndarray,
    y_pred: np.ndarray,
    shap_values: np.ndarray,
) -> dict:
    """Choose one useful test-row example for the local explanation."""
    case_table = pd.DataFrame(
        {
            "actual": y_test,
            "prediction": y_pred,
            "probability": y_proba,
        },
        index=X_test.index,
    )

    # Prefer a true failure row. If none exists, use the highest-risk row.
    failure_cases = case_table[case_table["actual"] == 1]
    selected_index = (
        failure_cases.sort_values("probability", ascending=False).index[0]
        if not failure_cases.empty
        else case_table.sort_values("probability", ascending=False).index[0]
    )

    shap_row = pd.Series(shap_values[X_test.index.get_loc(selected_index)], index=X_test.columns)
    top_features = (
        pd.DataFrame(
            {
                "feature": shap_row.index,
                "feature_value": X_test.loc[selected_index].values,
                "shap_value": shap_row.values,
                "abs_shap_value": np.abs(shap_row.values),
            }
        )
        .sort_values("abs_shap_value", ascending=False)
        .head(5)
    )

    raw_columns = [
        "UDI",
        "Product ID",
        "Type",
        "Air temperature [K]",
        "Process temperature [K]",
        "Rotational speed [rpm]",
        "Torque [Nm]",
        "Tool wear [min]",
        TARGET_COLUMN,
    ]
    raw_case = raw_df.loc[selected_index, [column for column in raw_columns if column in raw_df.columns]]

    return {
        "index": int(selected_index),
        "actual": int(case_table.loc[selected_index, "actual"]),
        "prediction": int(case_table.loc[selected_index, "prediction"]),
        "probability": float(case_table.loc[selected_index, "probability"]),
        "raw_case": raw_case.to_dict(),
        "top_features": top_features.to_dict(orient="records"),
    }


def save_local_case(case: dict, best_threshold: float, output_dir: Path) -> None:
    """Save one local explanation as both JSON and beginner-readable Markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "local_case_explanation.json"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(case, file, indent=2, ensure_ascii=False)

    lines = [
        "# Local XGBoost Failure Prediction Explanation",
        "",
        "## Selected Case",
        "",
        f"- Test row index: `{case['index']}`",
        f"- Actual Machine failure: `{case['actual']}`",
        f"- XGBoost prediction using threshold {best_threshold:.2f}: `{case['prediction']}`",
        f"- XGBoost failure probability: `{case['probability']:.4f}`",
        "",
        "## Raw Sensor Values",
        "",
    ]

    for key, value in case["raw_case"].items():
        lines.append(f"- {key}: `{value}`")

    lines += [
        "",
        "## Top SHAP Factors",
        "",
        "Positive SHAP values push the model toward failure. Negative SHAP values push the model toward normal.",
        "",
    ]

    for feature in case["top_features"]:
        direction = "failure" if feature["shap_value"] > 0 else "normal"
        lines.append(
            f"- `{feature['feature']}` = `{feature['feature_value']}` "
            f"has SHAP `{feature['shap_value']:.4f}`, pushing toward **{direction}**."
        )

    lines += [
        "",
        "## Presentation Memo",
        "",
        "This example connects the model output to sensor-level evidence. "
        "For the next stage, these top SHAP factors can be converted into a grounded LLM prompt, "
        "but no LLM is used in Stage 4.",
    ]

    markdown_path = output_dir / "local_case_explanation.md"
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Run Stage 4: threshold tuning and XGBoost SHAP explanation."""
    project_root = Path(__file__).resolve().parents[1]
    data_path = project_root / "data" / "ai4i2020.csv"
    output_dir = project_root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test, raw_df = prepare_train_test_data(
        csv_path=data_path,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    xgboost_model = build_models(y_train)["xgboost"]
    print("Training XGBoost for Stage 4 explanation...")
    xgboost_model.fit(X_train, y_train)

    y_proba = xgboost_model.predict_proba(X_test)[:, 1]
    threshold_metrics = evaluate_thresholds(y_test, y_proba)
    best_threshold_row = select_best_threshold(threshold_metrics)
    best_threshold = float(best_threshold_row["threshold"])
    y_pred_best = (y_proba >= best_threshold).astype(int)

    threshold_metrics.to_csv(output_dir / "threshold_metrics.csv", index=False, encoding="utf-8-sig")
    save_threshold_plot(threshold_metrics, best_threshold, output_dir / "threshold_tuning.png")

    threshold_summary = {
        "model": "xgboost",
        "selection_rule": "highest f1_score, then highest recall if tied",
        "threshold_search": {
            "start": 0.05,
            "end": 0.95,
            "step": 0.01,
        },
        "selected_threshold": round(best_threshold, 4),
        "selected_metrics": {
            "precision": float(best_threshold_row["precision"]),
            "recall": float(best_threshold_row["recall"]),
            "f1_score": float(best_threshold_row["f1_score"]),
        },
        "default_0_5_metrics": threshold_metrics.loc[
            threshold_metrics["threshold"] == 0.50,
            ["precision", "recall", "f1_score"],
        ].iloc[0].to_dict(),
        "test_rows": int(len(X_test)),
        "test_failures": int(y_test.sum()),
    }

    with (output_dir / "threshold_summary.json").open("w", encoding="utf-8") as file:
        json.dump(threshold_summary, file, indent=2, ensure_ascii=False)

    print("Calculating SHAP values for XGBoost...")
    shap_values = calculate_shap_values(xgboost_model, X_train, X_test)
    save_shap_plots(shap_values, X_test, output_dir)

    case = pick_explanation_case(
        raw_df=raw_df,
        X_test=X_test,
        y_test=y_test,
        y_proba=y_proba,
        y_pred=y_pred_best,
        shap_values=shap_values,
    )
    save_local_case(case, best_threshold, output_dir)

    print("Stage 4 explanation finished successfully.")
    print(f"Best threshold by F1-score: {best_threshold:.2f}")
    print(f"Threshold metrics saved to: {output_dir / 'threshold_metrics.csv'}")
    print(f"Threshold summary saved to: {output_dir / 'threshold_summary.json'}")
    print(f"Threshold plot saved to: {output_dir / 'threshold_tuning.png'}")
    print(f"SHAP summary saved to: {output_dir / 'shap_summary.png'}")
    print(f"SHAP bar plot saved to: {output_dir / 'shap_bar.png'}")
    print(f"Local case explanation saved to: {output_dir / 'local_case_explanation.md'}")


if __name__ == "__main__":
    main()
