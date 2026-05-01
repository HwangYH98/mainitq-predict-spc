from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from data import TARGET_COLUMN, prepare_train_test_data
from evaluate import calculate_metrics, save_confusion_matrix, save_metrics, save_pr_curve


RANDOM_STATE = 42
TEST_SIZE = 0.2


def build_models(y_train: pd.Series) -> dict:
    """Create the two baseline models used in the presentation."""
    positive_count = int(y_train.sum())
    negative_count = int(len(y_train) - positive_count)

    # XGBoost can use this value to pay more attention to rare failure rows.
    # This is not SMOTE. It only changes model weighting during training.
    scale_pos_weight = negative_count / positive_count if positive_count else 1.0

    logistic_regression = Pipeline(
        steps=[
            # Logistic Regression works better when numeric columns have similar scales.
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    solver="liblinear",
                ),
            ),
        ]
    )

    xgboost = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        scale_pos_weight=scale_pos_weight,
    )

    return {
        "logistic_regression": logistic_regression,
        "xgboost": xgboost,
    }


def main() -> None:
    """Run the complete baseline training pipeline."""
    project_root = Path(__file__).resolve().parents[1]
    data_path = project_root / "data" / "ai4i2020.csv"
    output_dir = project_root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test, raw_df = prepare_train_test_data(
        csv_path=data_path,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    models = build_models(y_train)
    evaluation_results = {}
    metrics_summary = {
        "dataset_path": str(data_path),
        "target_column": TARGET_COLUMN,
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "feature_count": int(X_train.shape[1]),
        "dropped_columns": ["UDI", "Product ID", "TWF", "HDF", "PWF", "OSF", "RNF"],
        "models": {},
    }

    # Keep identifiers in the prediction file so the test rows are easy to inspect.
    predictions_df = raw_df.loc[X_test.index, ["UDI", "Product ID", TARGET_COLUMN]].copy()
    predictions_df = predictions_df.rename(columns={TARGET_COLUMN: "actual_machine_failure"})

    for model_name, model in models.items():
        print(f"Training {model_name}...")
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        evaluation_results[model_name] = {
            "y_true": y_test,
            "y_pred": y_pred,
            "y_proba": y_proba,
        }
        metrics_summary["models"][model_name] = calculate_metrics(y_test, y_pred, y_proba)

        predictions_df[f"{model_name}_prediction"] = y_pred
        predictions_df[f"{model_name}_probability"] = y_proba

    metrics_summary["best_model_by_pr_auc"] = max(
        metrics_summary["models"],
        key=lambda model_name: metrics_summary["models"][model_name]["pr_auc"],
    )

    save_metrics(metrics_summary, output_dir / "metrics.json")
    save_confusion_matrix(evaluation_results, output_dir / "confusion_matrix.png")
    save_pr_curve(evaluation_results, output_dir / "pr_curve.png")

    predictions_df.sort_index().to_csv(
        output_dir / "baseline_predictions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("Baseline training finished successfully.")
    print(f"Metrics saved to: {output_dir / 'metrics.json'}")
    print(f"Confusion matrix saved to: {output_dir / 'confusion_matrix.png'}")
    print(f"PR curve saved to: {output_dir / 'pr_curve.png'}")
    print(f"Predictions saved to: {output_dir / 'baseline_predictions.csv'}")


if __name__ == "__main__":
    main()
