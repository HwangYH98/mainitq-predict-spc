import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier, XGBRegressor


matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

SPC_TIMESERIES_PATH = OUTPUT_DIR / "spc_timeseries.csv"
SPC_SUMMARY_PATH = OUTPUT_DIR / "spc_summary.json"
AI_CONTEXT_PATH = OUTPUT_DIR / "ai_report_context.json"
FUTURE_PREDICTIONS_PATH = OUTPUT_DIR / "future_deviation_predictions.csv"
FUTURE_METRICS_PATH = OUTPUT_DIR / "future_deviation_metrics.json"
FUTURE_CHART_PATH = OUTPUT_DIR / "future_deviation_chart.png"

HORIZON_STEPS = 10
VALIDATION_FRACTION = 0.25
RANDOM_STATE = 42


def require_file(path: Path) -> None:
    """Fail clearly when a prerequisite artifact is missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}\n"
            "Run train_baseline.py, stage4_explain.py, and predictive_spc.py first."
        )


def load_json(path: Path) -> dict:
    """Read a JSON artifact."""
    require_file(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    """Write a JSON artifact with readable formatting."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def future_window_frame(values: pd.Series, horizon_steps: int) -> pd.DataFrame:
    """Create columns containing the next 1..horizon values."""
    return pd.concat(
        [values.shift(-step).rename(f"t_plus_{step}") for step in range(1, horizon_steps + 1)],
        axis=1,
    )


def add_future_targets(spc_df: pd.DataFrame, horizon_steps: int) -> pd.DataFrame:
    """
    Add future risk and future deviation labels.

    AI4I has no real timestamp, so UDI order is treated as a simulated time axis.
    The target excludes the current row and looks only at the next horizon rows.
    """
    result = spc_df.copy()
    probabilities = result["xgboost_probability"].astype(float)
    threshold = result["selected_threshold"].astype(float)
    current_alert = (
        (probabilities >= threshold)
        | result["risk_beyond_control_limit"].astype(bool)
        | result["spc_risk_alert"].astype(bool)
    )

    future_risk_window = future_window_frame(probabilities, horizon_steps)
    future_alert_window = future_window_frame(current_alert.astype(int), horizon_steps)
    full_future_available = result.index <= (len(result) - horizon_steps - 1)

    result["future_max_risk_actual_h10"] = future_risk_window.max(axis=1)
    result["future_deviation_actual_h10"] = future_alert_window.max(axis=1)
    result.loc[~full_future_available, "future_max_risk_actual_h10"] = np.nan
    result.loc[~full_future_available, "future_deviation_actual_h10"] = np.nan
    result["target_available"] = full_future_available

    return result


def safe_column_name(column_name: str) -> str:
    """Make column names compact for the future prediction feature table."""
    return (
        column_name.lower()
        .replace("[", "")
        .replace("]", "")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
    )


def build_feature_frame(spc_df: pd.DataFrame) -> pd.DataFrame:
    """Create lag and rolling features using only current and past rows."""
    features = pd.DataFrame(index=spc_df.index)

    numeric_columns = [
        "time_step",
        "xgboost_probability",
        "risk_rolling_mean",
        "risk_ucl",
        "Torque [Nm]",
        "torque_rolling_mean",
        "torque_ucl",
        "torque_lcl",
        "Air temperature [K]",
        "Process temperature [K]",
        "Rotational speed [rpm]",
        "Tool wear [min]",
    ]
    for column in numeric_columns:
        features[safe_column_name(column)] = spc_df[column].astype(float)

    for column in [
        "xgboost_probability",
        "Torque [Nm]",
        "Rotational speed [rpm]",
        "Tool wear [min]",
    ]:
        base = spc_df[column].astype(float)
        name = safe_column_name(column)
        for lag in [1, 2, 3, 5, 10]:
            features[f"{name}_lag_{lag}"] = base.shift(lag)
        features[f"{name}_delta_1"] = base - base.shift(1)
        for window in [5, 10, 25, 50]:
            features[f"{name}_rolling_mean_{window}"] = base.rolling(
                window=window,
                min_periods=1,
            ).mean()
            features[f"{name}_rolling_std_{window}"] = base.rolling(
                window=window,
                min_periods=2,
            ).std()

    features["current_high_risk"] = (spc_df["risk_status"] == "High Risk").astype(int)
    features["current_spc_risk_alert"] = spc_df["spc_risk_alert"].astype(bool).astype(int)
    features["current_torque_limit_alert"] = (
        spc_df["torque_beyond_control_limit"].astype(bool).astype(int)
    )

    if "Type" in spc_df.columns:
        type_dummies = pd.get_dummies(spc_df["Type"], prefix="type", dtype=int)
        features = pd.concat([features, type_dummies], axis=1)

    # The first few rows do not have lag history. Use nearby history so the
    # live demo can still produce a prediction from row 1.
    features = features.ffill().bfill().fillna(0)
    return features


def chronological_split(valid_rows: pd.DataFrame) -> tuple[pd.Index, pd.Index]:
    """Split in time order so validation rows are later than training rows."""
    split_at = int(len(valid_rows) * (1 - VALIDATION_FRACTION))
    split_at = max(1, min(split_at, len(valid_rows) - 1))
    return valid_rows.index[:split_at], valid_rows.index[split_at:]


def safe_auc(metric_fn, y_true: pd.Series, y_score: np.ndarray) -> float | None:
    """Return None when AUC is undefined because only one class is present."""
    if len(set(pd.Series(y_true).astype(int).tolist())) < 2:
        return None
    return round(float(metric_fn(y_true, y_score)), 4)


def select_probability_threshold(y_true: pd.Series, y_score: np.ndarray) -> dict:
    """Select the classifier threshold with best validation F1-score."""
    rows = []
    for threshold in np.round(np.arange(0.05, 0.951, 0.01), 2):
        y_pred = (y_score >= threshold).astype(int)
        rows.append(
            {
                "threshold": float(threshold),
                "precision": float(precision_score(y_true, y_pred, zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, zero_division=0)),
                "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
            }
        )

    return sorted(rows, key=lambda item: (item["f1_score"], item["recall"]), reverse=True)[0]


def train_future_models(targeted_df: pd.DataFrame, features: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Train XGBoost regression/classification models for the 10-step future target."""
    valid_rows = targeted_df[targeted_df["target_available"]].copy()
    train_index, validation_index = chronological_split(valid_rows)

    X_train = features.loc[train_index]
    X_valid = features.loc[validation_index]
    y_reg_train = targeted_df.loc[train_index, "future_max_risk_actual_h10"].astype(float)
    y_reg_valid = targeted_df.loc[validation_index, "future_max_risk_actual_h10"].astype(float)
    y_cls_train = targeted_df.loc[train_index, "future_deviation_actual_h10"].astype(int)
    y_cls_valid = targeted_df.loc[validation_index, "future_deviation_actual_h10"].astype(int)

    regressor = XGBRegressor(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=RANDOM_STATE,
    )
    regressor.fit(X_train, y_reg_train)

    negative_count = int((y_cls_train == 0).sum())
    positive_count = int((y_cls_train == 1).sum())
    scale_pos_weight = negative_count / positive_count if positive_count else 1.0
    classifier = XGBClassifier(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        scale_pos_weight=scale_pos_weight,
    )
    classifier.fit(X_train, y_cls_train)

    predicted_future_risk = np.clip(regressor.predict(features), 0, 1)
    predicted_deviation_probability = classifier.predict_proba(features)[:, 1]
    valid_pred_probability = classifier.predict_proba(X_valid)[:, 1]
    selected_decision = select_probability_threshold(y_cls_valid, valid_pred_probability)
    selected_decision_threshold = float(selected_decision["threshold"])
    predicted_deviation = (
        predicted_deviation_probability >= selected_decision_threshold
    ).astype(int)

    output = targeted_df.copy()
    output["predicted_future_max_risk_h10"] = predicted_future_risk
    output["predicted_future_deviation_probability_h10"] = predicted_deviation_probability
    output["predicted_future_deviation_h10"] = predicted_deviation
    output["future_horizon_steps"] = HORIZON_STEPS

    valid_pred_risk = output.loc[validation_index, "predicted_future_max_risk_h10"].astype(float)
    valid_pred_probability = output.loc[
        validation_index,
        "predicted_future_deviation_probability_h10",
    ].astype(float)
    valid_pred_label = output.loc[validation_index, "predicted_future_deviation_h10"].astype(int)
    rmse = float(np.sqrt(mean_squared_error(y_reg_valid, valid_pred_risk)))

    metrics = {
        "source": "AI4I UDI-order simulated time-series future deviation prediction",
        "note": (
            "This is a simulated forecasting PoC. AI4I does not provide a real "
            "factory timestamp or live sensor stream."
        ),
        "horizon_steps": HORIZON_STEPS,
        "split": "chronological 75/25 validation split",
        "train_rows": int(len(train_index)),
        "validation_rows": int(len(validation_index)),
        "feature_count": int(features.shape[1]),
        "target_definition": {
            "future_max_risk_actual_h10": "max XGBoost failure probability over the next 10 simulated steps",
            "future_deviation_actual_h10": "1 if any next 10 steps cross threshold or SPC risk limit",
        },
        "regression": {
            "model": "XGBRegressor",
            "mae": round(float(mean_absolute_error(y_reg_valid, valid_pred_risk)), 4),
            "rmse": round(rmse, 4),
            "r2": round(float(r2_score(y_reg_valid, valid_pred_risk)), 4),
        },
        "classification": {
            "model": "XGBClassifier",
            "decision_threshold": round(selected_decision_threshold, 2),
            "positive_rate_validation": round(float(y_cls_valid.mean()), 4),
            "precision": round(float(precision_score(y_cls_valid, valid_pred_label, zero_division=0)), 4),
            "recall": round(float(recall_score(y_cls_valid, valid_pred_label, zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_cls_valid, valid_pred_label, zero_division=0)), 4),
            "roc_auc": safe_auc(roc_auc_score, y_cls_valid, valid_pred_probability),
            "pr_auc": safe_auc(average_precision_score, y_cls_valid, valid_pred_probability),
            "selection_rule": "highest validation f1_score, then highest recall if tied",
        },
        "summary": {
            "target_available_rows": int(output["target_available"].sum()),
            "predicted_future_deviation_rows": int(output["predicted_future_deviation_h10"].sum()),
            "max_predicted_future_risk": round(
                float(output["predicted_future_max_risk_h10"].max()),
                6,
            ),
            "max_predicted_future_risk_time_step": int(
                output.loc[output["predicted_future_max_risk_h10"].idxmax(), "time_step"]
            ),
        },
    }
    return output, metrics


def save_future_chart(predictions: pd.DataFrame, metrics: dict, output_path: Path) -> None:
    """Save an easy-to-read future risk comparison chart."""
    validation_start = metrics["train_rows"] + 1
    view = predictions[predictions["time_step"] >= validation_start].copy()
    view = view.head(350)
    threshold = float(view["selected_threshold"].iloc[0])

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(
        view["time_step"],
        view["future_max_risk_actual_h10"],
        color="#0f766e",
        linewidth=1.6,
        label="Actual future max risk (next 10 steps)",
    )
    ax.plot(
        view["time_step"],
        view["predicted_future_max_risk_h10"],
        color="#b42318",
        linewidth=1.6,
        label="Predicted future max risk",
    )
    ax.axhline(
        threshold,
        color="#344054",
        linestyle="--",
        linewidth=1.2,
        label="Selected threshold",
    )
    predicted_alerts = view[view["predicted_future_deviation_h10"] == 1]
    if not predicted_alerts.empty:
        ax.scatter(
            predicted_alerts["time_step"],
            predicted_alerts["predicted_future_max_risk_h10"],
            color="#c97700",
            s=24,
            label="Predicted future deviation",
            zorder=5,
        )

    ax.set_title("Future 10-Step Deviation Prediction over Simulated Time")
    ax.set_xlabel("Simulated time step by UDI order")
    ax.set_ylabel("Future risk probability")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def future_context_for_time_step(predictions: pd.DataFrame, time_step: int) -> dict:
    """Build the small future-prediction block used by the AI report."""
    row = predictions[predictions["time_step"] == time_step]
    if row.empty:
        return {}

    selected = row.iloc[0]
    actual_value = selected.get("future_deviation_actual_h10")
    return {
        "horizon_steps": int(selected["future_horizon_steps"]),
        "predicted_future_max_risk_h10": round(
            float(selected["predicted_future_max_risk_h10"]),
            6,
        ),
        "predicted_future_deviation_probability_h10": round(
            float(selected["predicted_future_deviation_probability_h10"]),
            6,
        ),
        "predicted_future_deviation_h10": bool(selected["predicted_future_deviation_h10"]),
        "actual_future_deviation_h10": None
        if pd.isna(actual_value)
        else bool(int(actual_value)),
        "target_available": bool(selected["target_available"]),
    }


def update_spc_summary(metrics: dict) -> None:
    """Add future deviation summary values to the existing SPC JSON."""
    spc_summary = load_json(SPC_SUMMARY_PATH)
    spc_summary["future_deviation"] = {
        "horizon_steps": int(metrics["horizon_steps"]),
        "predicted_future_deviation_rows": int(
            metrics["summary"]["predicted_future_deviation_rows"]
        ),
        "max_predicted_future_risk": float(metrics["summary"]["max_predicted_future_risk"]),
        "max_predicted_future_risk_time_step": int(
            metrics["summary"]["max_predicted_future_risk_time_step"]
        ),
        "classification_f1_score": metrics["classification"]["f1_score"],
        "regression_rmse": metrics["regression"]["rmse"],
    }
    write_json(SPC_SUMMARY_PATH, spc_summary)


def update_ai_report_with_future(predictions: pd.DataFrame, metrics: dict) -> None:
    """Attach future prediction evidence to the saved AI report context."""
    if not AI_CONTEXT_PATH.exists():
        return

    from predictive_spc import genai_ai_report, save_ai_report

    context = load_json(AI_CONTEXT_PATH)
    time_step = int(context.get("row", {}).get("time_step", 0))
    context["future_prediction"] = future_context_for_time_step(predictions, time_step)
    context["future_deviation_metrics"] = {
        "horizon_steps": int(metrics["horizon_steps"]),
        "validation_f1_score": metrics["classification"]["f1_score"],
        "validation_pr_auc": metrics["classification"]["pr_auc"],
        "regression_rmse": metrics["regression"]["rmse"],
    }
    context["guardrail"] = (
        "Use the current risk, future 10-step deviation prediction, and SHAP "
        "evidence only as a manager reference. Do not write an automatic "
        "maintenance order."
    )
    report, mode = genai_ai_report(context)
    save_ai_report(context, report, mode)


def create_future_deviation_outputs() -> dict:
    """Create future-deviation CSV, metrics JSON, chart, and AI report context."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    require_file(SPC_TIMESERIES_PATH)

    spc_df = pd.read_csv(SPC_TIMESERIES_PATH)
    targeted_df = add_future_targets(spc_df, HORIZON_STEPS)
    features = build_feature_frame(targeted_df)
    predictions, metrics = train_future_models(targeted_df, features)

    predictions.to_csv(FUTURE_PREDICTIONS_PATH, index=False, encoding="utf-8-sig")
    write_json(FUTURE_METRICS_PATH, metrics)
    save_future_chart(predictions, metrics, FUTURE_CHART_PATH)
    update_spc_summary(metrics)
    update_ai_report_with_future(predictions, metrics)

    return {
        "future_predictions": str(FUTURE_PREDICTIONS_PATH),
        "future_metrics": str(FUTURE_METRICS_PATH),
        "future_chart": str(FUTURE_CHART_PATH),
        "horizon_steps": HORIZON_STEPS,
    }


def main() -> None:
    """Command-line entry point used by run_all.bat."""
    outputs = create_future_deviation_outputs()
    print("Future deviation prediction outputs created successfully.")
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
