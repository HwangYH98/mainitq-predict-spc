import json
from pathlib import Path
import re

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from evaluate import calculate_metrics
from train_baseline import RANDOM_STATE, TEST_SIZE, build_models


UNIT_PRESETS = {
    "No conversion": {"multiplier": 1.0, "offset": 0.0},
    "Celsius -> Kelvin": {"multiplier": 1.0, "offset": 273.15},
    "Kelvin -> Celsius": {"multiplier": 1.0, "offset": -273.15},
    "Percent -> Ratio": {"multiplier": 0.01, "offset": 0.0},
    "Ratio -> Percent": {"multiplier": 100.0, "offset": 0.0},
    "Milliseconds -> Seconds": {"multiplier": 0.001, "offset": 0.0},
    "Seconds -> Minutes": {"multiplier": 1.0 / 60.0, "offset": 0.0},
}

POSITIVE_LABELS = {
    "1",
    "true",
    "t",
    "yes",
    "y",
    "failure",
    "fail",
    "fault",
    "defect",
    "defective",
    "abnormal",
    "ng",
    "bad",
    "risk",
    "high_risk",
    "고장",
    "불량",
    "이상",
    "위험",
}

NEGATIVE_LABELS = {
    "0",
    "false",
    "f",
    "no",
    "n",
    "normal",
    "ok",
    "pass",
    "good",
    "healthy",
    "정상",
    "양품",
}


def clean_feature_name(column_name: str) -> str:
    """Make company column names safe for model feature names."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", str(column_name))
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").lower()
    return cleaned or "feature"


def make_unique_column_names(column_names: list[str]) -> list[str]:
    """Avoid duplicate names after cleaning and one-hot encoding."""
    seen = {}
    unique_names = []
    for column_name in column_names:
        base_name = clean_feature_name(column_name)
        count = seen.get(base_name, 0)
        seen[base_name] = count + 1
        unique_names.append(base_name if count == 0 else f"{base_name}_{count + 1}")
    return unique_names


def normalize_binary_target(target: pd.Series) -> pd.Series:
    """
    Convert common factory labels into binary 0/1 values.

    This intentionally accepts only clear binary labels so a mislabeled company
    dataset fails loudly instead of creating misleading model results.
    """
    if target.isna().any():
        missing_count = int(target.isna().sum())
        raise ValueError(f"Target column has {missing_count} missing values.")

    numeric_target = pd.to_numeric(target, errors="coerce")
    if numeric_target.notna().all():
        unique_values = sorted(numeric_target.unique().tolist())
        if set(unique_values).issubset({0, 1, 0.0, 1.0}):
            return numeric_target.astype(int)
        raise ValueError(
            "Numeric target must already be binary 0/1. "
            f"Found values: {unique_values[:10]}"
        )

    normalized = target.astype(str).str.strip().str.lower()
    unknown_values = sorted(
        value
        for value in normalized.unique().tolist()
        if value not in POSITIVE_LABELS and value not in NEGATIVE_LABELS
    )
    if unknown_values:
        raise ValueError(
            "Target labels must be clear binary labels such as 0/1, ok/ng, "
            f"normal/failure, or pass/fail. Unsupported labels: {unknown_values[:10]}"
        )

    return normalized.map(lambda value: 1 if value in POSITIVE_LABELS else 0).astype(int)


def apply_unit_conversions(
    feature_df: pd.DataFrame,
    unit_conversions: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Apply multiplier/offset unit conversions to selected numeric columns."""
    transformed = feature_df.copy()
    unit_conversions = unit_conversions or {}

    for column_name, conversion in unit_conversions.items():
        if column_name not in transformed.columns:
            raise ValueError(f"Unit conversion column is missing: {column_name}")

        multiplier = float(conversion.get("multiplier", 1.0))
        offset = float(conversion.get("offset", 0.0))
        numeric_values = pd.to_numeric(transformed[column_name], errors="coerce")
        if numeric_values.isna().all():
            raise ValueError(f"Column cannot be converted to numeric: {column_name}")

        transformed[column_name] = numeric_values * multiplier + offset

    return transformed


def prepare_company_features(
    df: pd.DataFrame,
    target_column: str,
    id_time_columns: list[str] | None = None,
    unit_conversions: dict[str, dict] | None = None,
) -> tuple[pd.DataFrame, pd.Series, dict]:
    """Build model-ready features from a labeled company CSV."""
    id_time_columns = id_time_columns or []
    missing_columns = [
        column
        for column in [target_column, *id_time_columns]
        if column and column not in df.columns
    ]
    if missing_columns:
        raise ValueError(f"Missing selected columns: {missing_columns}")

    y = normalize_binary_target(df[target_column])
    feature_columns = [
        column
        for column in df.columns
        if column != target_column and column not in id_time_columns
    ]
    if not feature_columns:
        raise ValueError("At least one feature column is required for retraining.")

    raw_features = df[feature_columns].copy()
    transformed_features = apply_unit_conversions(raw_features, unit_conversions)

    numeric_columns = []
    for column_name in transformed_features.columns:
        numeric_values = pd.to_numeric(transformed_features[column_name], errors="coerce")
        if pd.api.types.is_numeric_dtype(transformed_features[column_name]) or numeric_values.notna().mean() >= 0.8:
            numeric_columns.append(column_name)
    for column_name in numeric_columns:
        numeric_values = pd.to_numeric(transformed_features[column_name], errors="coerce")
        fill_value = float(numeric_values.median()) if numeric_values.notna().any() else 0.0
        transformed_features[column_name] = numeric_values.fillna(fill_value)

    categorical_columns = [
        column_name
        for column_name in transformed_features.columns
        if column_name not in numeric_columns
    ]
    for column_name in categorical_columns:
        transformed_features[column_name] = (
            transformed_features[column_name]
            .fillna("missing")
            .astype(str)
            .str.strip()
            .replace("", "missing")
        )

    X = pd.get_dummies(transformed_features, columns=categorical_columns, dtype=int)
    X.columns = make_unique_column_names(X.columns.tolist())

    feature_schema = {
        "target_column": target_column,
        "id_time_columns": id_time_columns,
        "original_feature_columns": feature_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "encoded_feature_columns": X.columns.tolist(),
        "unit_conversions": unit_conversions or {},
    }
    return X, y, feature_schema


def select_best_threshold(y_true: pd.Series, y_proba: np.ndarray) -> tuple[pd.DataFrame, dict]:
    """Sweep XGBoost probabilities and select the best threshold by F1."""
    rows = []
    for threshold in np.arange(0.05, 0.951, 0.01):
        y_pred = (y_proba >= threshold).astype(int)
        rows.append(
            {
                "threshold": round(float(threshold), 2),
                "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
                "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
            }
        )

    threshold_metrics = pd.DataFrame(rows)
    best_row = threshold_metrics.sort_values(
        ["f1_score", "recall"],
        ascending=[False, False],
    ).iloc[0]
    default_row = threshold_metrics.loc[threshold_metrics["threshold"] == 0.5].iloc[0]

    summary = {
        "model": "xgboost",
        "selection_rule": "highest f1_score, then highest recall if tied",
        "threshold_search": {"start": 0.05, "end": 0.95, "step": 0.01},
        "selected_threshold": float(best_row["threshold"]),
        "selected_metrics": {
            "precision": float(best_row["precision"]),
            "recall": float(best_row["recall"]),
            "f1_score": float(best_row["f1_score"]),
        },
        "default_0_5_metrics": {
            "precision": float(default_row["precision"]),
            "recall": float(default_row["recall"]),
            "f1_score": float(default_row["f1_score"]),
        },
        "test_rows": int(len(y_true)),
        "test_failures": int(y_true.sum()),
    }
    return threshold_metrics, summary


def calculate_shap_summary(model, X_test: pd.DataFrame, max_rows: int = 500) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate SHAP values and a compact feature-importance summary."""
    import shap

    sample = X_test.head(max_rows).copy()
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    shap_df = pd.DataFrame(shap_values, columns=sample.columns, index=sample.index)
    top_features = (
        shap_df.abs()
        .mean()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
        .rename(columns={"index": "feature", 0: "mean_abs_shap"})
    )
    top_features["mean_abs_shap"] = top_features["mean_abs_shap"].round(6)
    return shap_df, top_features


def plot_custom_shap_bar(top_features: pd.DataFrame, output_path: str | Path) -> None:
    """Save a SHAP-style bar chart for the company retraining run."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_df = top_features.sort_values("mean_abs_shap", ascending=True)
    plt.figure(figsize=(9, 6))
    plt.barh(plot_df["feature"], plot_df["mean_abs_shap"], color="#0f766e")
    plt.xlabel("Mean absolute SHAP value")
    plt.ylabel("Feature")
    plt.title("Company Retraining SHAP Feature Importance")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def train_custom_company_model(
    df: pd.DataFrame,
    target_column: str,
    id_time_columns: list[str] | None = None,
    unit_conversions: dict[str, dict] | None = None,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> dict:
    """Train Logistic Regression and XGBoost on a labeled company CSV."""
    X, y, feature_schema = prepare_company_features(
        df,
        target_column=target_column,
        id_time_columns=id_time_columns,
        unit_conversions=unit_conversions,
    )

    target_counts = y.value_counts().to_dict()
    if len(target_counts) != 2:
        raise ValueError(f"Target must contain both classes 0 and 1. Found: {target_counts}")
    if min(target_counts.values()) < 2:
        raise ValueError(
            "Each target class needs at least 2 rows for stratified train/test split. "
            f"Found: {target_counts}"
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )

    models = build_models(y_train)
    evaluation_results = {}
    metrics_summary = {
        "source": "custom_company_csv",
        "target_column": target_column,
        "id_time_columns": id_time_columns or [],
        "test_size": test_size,
        "random_state": random_state,
        "source_rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "feature_count": int(X_train.shape[1]),
        "target_counts": {str(key): int(value) for key, value in target_counts.items()},
        "models": {},
    }

    preserved_columns = [*(id_time_columns or []), target_column]
    predictions_df = df.loc[X_test.index, preserved_columns].copy()
    predictions_df = predictions_df.rename(columns={target_column: "actual_target_original"})
    predictions_df.insert(0, "input_index", X_test.index.astype(int))
    predictions_df["actual_binary_target"] = y_test.astype(int).values

    for model_name, model in models.items():
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

    threshold_metrics, threshold_summary = select_best_threshold(
        y_test,
        predictions_df["xgboost_probability"].to_numpy(),
    )
    selected_threshold = float(threshold_summary["selected_threshold"])
    predictions_df["xgboost_prediction_by_selected_threshold"] = (
        predictions_df["xgboost_probability"] >= selected_threshold
    ).astype(int)
    predictions_df["risk_status"] = np.where(
        predictions_df["xgboost_prediction_by_selected_threshold"] == 1,
        "High Risk",
        "Normal",
    )

    shap_values, top_features = calculate_shap_summary(models["xgboost"], X_test)
    mapping = {
        "target_column": target_column,
        "target_positive_examples": sorted(POSITIVE_LABELS),
        "target_negative_examples": sorted(NEGATIVE_LABELS),
        "id_time_columns": id_time_columns or [],
        "unit_conversions": unit_conversions or {},
        "note": "This is a local retraining PoC for labeled company CSV data.",
    }

    return {
        "models": models,
        "metrics": metrics_summary,
        "threshold_metrics": threshold_metrics,
        "threshold_summary": threshold_summary,
        "predictions": predictions_df.sort_values("xgboost_probability", ascending=False),
        "feature_schema": feature_schema,
        "mapping": mapping,
        "shap_values": shap_values,
        "shap_top_features": top_features,
        "X_test": X_test,
        "y_test": y_test,
    }


def save_custom_training_outputs(result: dict, output_dir: str | Path) -> dict[str, str]:
    """Persist a company retraining run for presentation and later review."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "mapping": output_dir / "mapping.json",
        "feature_schema": output_dir / "feature_schema.json",
        "metrics": output_dir / "custom_metrics.json",
        "threshold_summary": output_dir / "custom_threshold_summary.json",
        "threshold_metrics": output_dir / "custom_threshold_metrics.csv",
        "predictions": output_dir / "custom_predictions.csv",
        "xgboost_model": output_dir / "xgboost_model.joblib",
        "logistic_model": output_dir / "logistic_model.joblib",
        "shap_bar": output_dir / "custom_shap_bar.png",
    }

    for key in ["mapping", "feature_schema", "metrics", "threshold_summary"]:
        value_key = {
            "metrics": "metrics",
            "threshold_summary": "threshold_summary",
        }.get(key, key)
        with paths[key].open("w", encoding="utf-8") as file:
            json.dump(result[value_key], file, indent=2, ensure_ascii=False)

    result["threshold_metrics"].to_csv(paths["threshold_metrics"], index=False, encoding="utf-8-sig")
    result["predictions"].to_csv(paths["predictions"], index=False, encoding="utf-8-sig")
    joblib.dump(result["models"]["xgboost"], paths["xgboost_model"])
    joblib.dump(result["models"]["logistic_regression"], paths["logistic_model"])
    plot_custom_shap_bar(result["shap_top_features"], paths["shap_bar"])

    return {key: str(path) for key, path in paths.items()}
