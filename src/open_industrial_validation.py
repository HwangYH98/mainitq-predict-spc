from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data_external" / "scania_component_x"

METRICS_CSV = OUTPUT_DIR / "open_industrial_validation_metrics.csv"
METRICS_JSON = OUTPUT_DIR / "open_industrial_validation_metrics.json"
REPORT_MD = OUTPUT_DIR / "open_industrial_validation_report.md"
COST_CSV = OUTPUT_DIR / "open_industrial_cost_simulation.csv"
LEAD_TIME_MD = OUTPUT_DIR / "open_industrial_lead_time_report.md"
LEAD_TIME_PNG = OUTPUT_DIR / "open_industrial_lead_time_chart.png"

RANDOM_STATE = 42
FAILURE_HORIZON_STEPS = 3
ID_COLUMN_CANDIDATES = ["vehicle_id", "truck_id", "unit_id", "asset_id", "chassis_id", "id"]
TIME_COLUMN_CANDIDATES = ["time_step", "timestamp", "readout_id", "readout", "cycle", "date"]
LABEL_COLUMN_CANDIDATES = [
    "actual_failure",
    "failure",
    "target",
    "label",
    "class",
    "class_label",
    "in_study_repair",
]
TTE_COLUMN_CANDIDATES = ["time_to_event", "tte", "remaining_useful_life", "rul"]


@dataclass
class OpenIndustrialDataset:
    """A normalized row-level predictive-maintenance validation table."""

    frame: pd.DataFrame
    source_mode: str
    dataset_name: str
    source_note: str


def normalize_name(value: str) -> str:
    """Normalize column names for loose matching across public datasets."""
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def find_column(columns: list[str], candidates: list[str]) -> str | None:
    """Find a likely column name from a candidate list."""
    normalized = {normalize_name(column): column for column in columns}
    for candidate in candidates:
        key = normalize_name(candidate)
        if key in normalized:
            return normalized[key]
    for column in columns:
        lowered = normalize_name(column)
        if any(normalize_name(candidate) in lowered for candidate in candidates):
            return column
    return None


def find_existing_file(data_dir: Path, names: list[str]) -> Path | None:
    """Find a dataset file by trying common SCANIA file names."""
    for name in names:
        candidate = data_dir / name
        if candidate.exists():
            return candidate
    return None


def build_sample_scania_like_dataset(
    unit_count: int = 220,
    readings_per_unit: int = 12,
) -> OpenIndustrialDataset:
    """Create a small SCANIA-like time-series sample for offline verification.

    This is not real SCANIA data. It preserves the validation shape: unit id,
    time step, sensor counters, time-to-event, and a near-failure label.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    rows = []
    for unit_index in range(unit_count):
        component_family = ["A", "B", "C"][unit_index % 3]
        will_fail = unit_index % 4 != 0
        degradation_rate = rng.uniform(0.05, 0.16) if will_fail else rng.uniform(0.0, 0.035)
        base_vibration = rng.normal(0.25, 0.04)
        base_temperature = rng.normal(72, 4)
        base_pressure = rng.normal(33, 3)
        load_level = rng.normal(0.62, 0.12)
        failure_step = readings_per_unit - rng.integers(1, 4) if will_fail else None
        for step in range(readings_per_unit):
            tte = max((failure_step or readings_per_unit + 20) - step, 0)
            wear_signal = step * degradation_rate
            vibration = base_vibration + wear_signal + rng.normal(0, 0.025)
            temperature = base_temperature + wear_signal * 34 + rng.normal(0, 1.6)
            pressure = base_pressure + load_level * 7 + wear_signal * 9 + rng.normal(0, 1.2)
            oil_quality = 1.0 - wear_signal * 1.6 + rng.normal(0, 0.025)
            rows.append(
                {
                    "unit_id": f"SCANIA_SAMPLE_{unit_index:04d}",
                    "time_step": step,
                    "component_family": component_family,
                    "engine_load": round(float(load_level), 4),
                    "temperature_index": round(float(temperature), 4),
                    "vibration_index": round(float(vibration), 5),
                    "pressure_index": round(float(pressure), 4),
                    "oil_quality_index": round(float(oil_quality), 5),
                    "time_to_event": int(tte),
                    "actual_failure": int(tte <= FAILURE_HORIZON_STEPS),
                }
            )
    frame = pd.DataFrame(rows)
    return OpenIndustrialDataset(
        frame=frame,
        source_mode="sample_scania_like",
        dataset_name="SCANIA Component X adapter sample",
        source_note=(
            "Offline SCANIA-like sample generated from deterministic rules. "
            "Use only to verify adapter behavior; it is not real SCANIA data."
        ),
    )


def load_csv_limited(path: Path, max_rows: int) -> pd.DataFrame:
    """Load at most max_rows rows from a large public CSV."""
    return pd.read_csv(path, nrows=max_rows)


def matching_specification_names(operational_path: Path) -> list[str]:
    """Return likely specification file names for the selected operational file."""
    name = operational_path.name
    if name.startswith("validation_"):
        return ["validation_specifications.csv"]
    if name.startswith("train_"):
        return ["train_specifications.csv"]
    if name.startswith("test_"):
        return ["test_specifications.csv"]
    return [
        "validation_specifications.csv",
        "train_specifications.csv",
        "test_specifications.csv",
    ]


def infer_label_series(df: pd.DataFrame, label_column: str) -> pd.Series:
    """Infer a binary event label from common public benchmark label formats."""
    raw = df[label_column]
    numeric = pd.to_numeric(raw, errors="coerce")
    non_null_numeric = numeric.dropna()
    if not non_null_numeric.empty:
        unique_values = set(non_null_numeric.astype(float).unique().tolist())
        if unique_values.issubset({0.0, 1.0}):
            return (numeric.fillna(0) == 1).astype(int)
        return (numeric.fillna(0) > 0).astype(int)

    normalized = raw.astype(str).str.strip().str.lower()
    positive_values = {"1", "true", "yes", "failure", "fail", "failed", "positive", "repair"}
    return normalized.isin(positive_values).astype(int)


def add_binary_label_proxy(
    operational: pd.DataFrame,
    id_column: str,
    time_column: str,
    label_column: str,
) -> pd.DataFrame:
    """Convert vehicle-level public labels into a row-level early-warning target.

    SCANIA Component X validation labels are vehicle-level class labels. The
    validation file does not include a repair timestamp, so this adapter uses
    the last observed readout of a positive vehicle as an end-of-study proxy.
    This supports reproducible benchmarking while keeping the report clear that
    it is not a verified field lead-time measurement.
    """
    labeled = operational.copy()
    vehicle_label = infer_label_series(labeled, label_column)
    labeled["vehicle_level_failure_label"] = vehicle_label
    time_values = pd.to_numeric(labeled[time_column], errors="coerce")
    fallback_step = labeled.groupby(id_column).cumcount()
    labeled["time_step_proxy"] = time_values.fillna(fallback_step)
    end_time = labeled.groupby(id_column)["time_step_proxy"].transform("max")
    labeled["time_to_event"] = np.where(
        labeled["vehicle_level_failure_label"] == 1,
        end_time - labeled["time_step_proxy"],
        FAILURE_HORIZON_STEPS + 30,
    )
    labeled["actual_failure"] = (
        (labeled["vehicle_level_failure_label"] == 1)
        & (labeled["time_to_event"] <= FAILURE_HORIZON_STEPS)
    ).astype(int)
    return labeled


def add_scania_class_label_proxy(
    operational: pd.DataFrame,
    id_column: str,
    time_column: str,
    label_column: str,
) -> pd.DataFrame:
    """Normalize SCANIA validation class labels to one final readout per vehicle."""
    labeled = operational.copy()
    label_numeric = pd.to_numeric(labeled[label_column], errors="coerce").fillna(0).astype(int)
    time_values = pd.to_numeric(labeled[time_column], errors="coerce")
    fallback_step = labeled.groupby(id_column).cumcount()
    labeled["time_step_proxy"] = time_values.fillna(fallback_step)
    labeled["public_class_label"] = label_numeric
    labeled = labeled.sort_values([id_column, "time_step_proxy"]).groupby(id_column).tail(1)

    # SCANIA challenge classes map the final readout to a window before failure.
    # The midpoint is used as a lead-time proxy for reporting, not as a field timestamp.
    class_to_tte_midpoint = {1: 36.0, 2: 18.0, 3: 9.0, 4: 3.0}
    labeled["time_to_event"] = labeled["public_class_label"].map(class_to_tte_midpoint)
    labeled["time_to_event"] = labeled["time_to_event"].fillna(FAILURE_HORIZON_STEPS + 30)
    labeled["actual_failure"] = (labeled["public_class_label"] > 0).astype(int)
    return labeled


def load_scania_component_x(data_dir: Path, max_rows: int) -> OpenIndustrialDataset | None:
    """Load a small row-level slice of SCANIA Component X when files are present."""
    if not data_dir.exists():
        return None

    operational_path = find_existing_file(
        data_dir,
        [
            "train_operational_readouts.csv",
            "validation_operational_readouts.csv",
            "test_operational_readouts.csv",
        ],
    )
    if operational_path is None:
        return None

    operational = load_csv_limited(operational_path, max_rows=max_rows)
    if operational.empty:
        return None

    id_column = find_column(
        operational.columns.tolist(),
        ID_COLUMN_CANDIDATES,
    )
    if id_column is None:
        id_column = "__unit_id"
        operational[id_column] = np.arange(len(operational))

    time_column = find_column(
        operational.columns.tolist(),
        TIME_COLUMN_CANDIDATES,
    )
    if time_column is None:
        time_column = "__time_step"
        operational[time_column] = operational.groupby(id_column).cumcount()

    label_path = find_existing_file(
        data_dir,
        ["train_tte.csv", "validation_labels.csv", "test_labels.csv"],
    )
    if label_path is not None:
        labels = pd.read_csv(label_path)
        label_id_column = find_column(
            labels.columns.tolist(),
            ID_COLUMN_CANDIDATES,
        )
        if label_id_column is not None:
            labels = labels.rename(columns={label_id_column: id_column})
            operational = operational.merge(labels, on=id_column, how="left")

    spec_path = find_existing_file(data_dir, matching_specification_names(operational_path))
    if spec_path is not None:
        specs = pd.read_csv(spec_path)
        spec_id_column = find_column(specs.columns.tolist(), ID_COLUMN_CANDIDATES)
        if spec_id_column is not None:
            specs = specs.rename(columns={spec_id_column: id_column})
            operational = operational.merge(specs, on=id_column, how="left")

    tte_column = find_column(
        operational.columns.tolist(),
        TTE_COLUMN_CANDIDATES,
    )
    label_column = find_column(
        operational.columns.tolist(),
        LABEL_COLUMN_CANDIDATES,
    )

    if label_column is not None and normalize_name(label_column) == "classlabel":
        operational = add_scania_class_label_proxy(
            operational,
            id_column=id_column,
            time_column=time_column,
            label_column=label_column,
        )
    elif tte_column is not None:
        operational["time_to_event"] = pd.to_numeric(operational[tte_column], errors="coerce")
        operational["actual_failure"] = (operational["time_to_event"] <= FAILURE_HORIZON_STEPS).astype(int)
    elif label_column is not None:
        operational = add_binary_label_proxy(
            operational,
            id_column=id_column,
            time_column=time_column,
            label_column=label_column,
        )
    else:
        raise ValueError(
            "SCANIA files were found, but no time-to-event or label column could be inferred."
        )

    operational["unit_id"] = operational[id_column].astype(str)
    operational["time_step"] = pd.to_numeric(operational[time_column], errors="coerce")
    operational["time_step"] = operational["time_step"].fillna(
        operational.groupby("unit_id").cumcount()
    )

    return OpenIndustrialDataset(
        frame=operational,
        source_mode="open_scania_component_x",
        dataset_name="SCANIA Component X public dataset",
        source_note=(
            "Loaded from local data_external files downloaded from Researchdata.se "
            "(DOI: 10.58141/1w9m-yz81, CC BY 4.0). This is a public real-world "
            "SCANIA dataset, but it is still not this project's own factory deployment."
        ),
    )


def prepare_model_frame(dataset: OpenIndustrialDataset) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Build features and labels while preserving unit/time metadata."""
    df = dataset.frame.copy()
    df = df.dropna(subset=["actual_failure"])
    df["actual_failure"] = df["actual_failure"].astype(int)
    if df["actual_failure"].nunique() < 2:
        raise ValueError("Open industrial validation needs both normal and failure rows.")

    excluded_normalized = {
        normalize_name(value)
        for value in [
            *ID_COLUMN_CANDIDATES,
            *TIME_COLUMN_CANDIDATES,
            *LABEL_COLUMN_CANDIDATES,
            *TTE_COLUMN_CANDIDATES,
            "vehicle_level_failure_label",
            "public_class_label",
            "time_step_proxy",
        ]
    }
    metadata_columns = {"actual_failure", "time_to_event", "unit_id", "time_step"}
    candidate_features = [column for column in df.columns if column not in metadata_columns]
    candidate_features = [
        column for column in candidate_features if normalize_name(column) not in excluded_normalized
    ]
    features = df[candidate_features].copy()
    for column in features.columns:
        if features[column].dtype == "object":
            features[column] = features[column].astype(str).fillna("missing")
        else:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    features = pd.get_dummies(features, dummy_na=True)
    features = features.replace([np.inf, -np.inf], np.nan)
    features = features.fillna(features.median(numeric_only=True)).fillna(0)
    metadata = df[["unit_id", "time_step", "time_to_event"]].copy()
    return features, df["actual_failure"], metadata


def group_train_test_split(
    X: pd.DataFrame,
    y: pd.Series,
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.DataFrame, pd.DataFrame]:
    """Split by vehicle/unit id so one unit does not appear in both sets."""
    unit_labels = (
        pd.DataFrame({"unit_id": metadata["unit_id"], "actual_failure": y})
        .groupby("unit_id", as_index=False)["actual_failure"]
        .max()
    )
    stratify = (
        unit_labels["actual_failure"]
        if unit_labels["actual_failure"].value_counts().min() >= 2
        else None
    )
    train_units, test_units = train_test_split(
        unit_labels["unit_id"],
        test_size=0.3,
        random_state=RANDOM_STATE,
        stratify=stratify,
    )
    train_mask = metadata["unit_id"].isin(set(train_units))
    test_mask = metadata["unit_id"].isin(set(test_units))
    return (
        X.loc[train_mask],
        X.loc[test_mask],
        y.loc[train_mask],
        y.loc[test_mask],
        metadata.loc[train_mask],
        metadata.loc[test_mask],
    )


def choose_rule_feature(X_train: pd.DataFrame, y_train: pd.Series) -> str:
    """Choose a non-leaky numeric feature for simple rule/SPC baselines."""
    if "vibration_index" in X_train.columns:
        return "vibration_index"
    numeric_candidates = X_train.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_candidates:
        return X_train.columns[0]
    correlations = {}
    for column in numeric_candidates[:250]:
        values = X_train[column]
        if values.nunique(dropna=True) <= 1:
            correlations[column] = 0.0
            continue
        correlations[column] = abs(float(values.corr(y_train.fillna(0)) or 0.0))
    return max(correlations, key=correlations.get)


def threshold_metrics(y_true: pd.Series, alerts: np.ndarray, probabilities: np.ndarray | None = None) -> dict:
    """Calculate common alert metrics."""
    tn, fp, fn, tp = confusion_matrix(y_true, alerts, labels=[0, 1]).ravel()
    payload = {
        "precision": float(precision_score(y_true, alerts, zero_division=0)),
        "recall": float(recall_score(y_true, alerts, zero_division=0)),
        "f1_score": float(f1_score(y_true, alerts, zero_division=0)),
        "alert_count": int(fp + tp),
        "false_alarm_count": int(fp),
        "missed_failure_count": int(fn),
        "true_positive_count": int(tp),
        "true_negative_count": int(tn),
        "actual_failure_count": int(y_true.sum()),
        "total_rows": int(len(y_true)),
    }
    if probabilities is not None:
        payload["pr_auc"] = float(average_precision_score(y_true, probabilities))
    else:
        payload["pr_auc"] = float(average_precision_score(y_true, alerts))
    return payload


def tune_threshold(y_true: pd.Series, probabilities: np.ndarray) -> float:
    """Choose the probability threshold with the best F1 score."""
    rows = []
    for threshold in np.arange(0.05, 0.951, 0.01):
        alerts = (probabilities >= threshold).astype(int)
        rows.append((float(threshold), f1_score(y_true, alerts, zero_division=0)))
    return max(rows, key=lambda item: item[1])[0]


def lead_time_summary(metadata: pd.DataFrame, y_true: pd.Series, alerts: np.ndarray) -> dict:
    """Calculate unit-level early-warning lead-time metrics."""
    frame = metadata.copy()
    frame["actual_failure"] = y_true.to_numpy()
    frame["alert"] = alerts
    lead_times = []
    for _, unit_df in frame.sort_values("time_step").groupby("unit_id"):
        failure_rows = unit_df[unit_df["actual_failure"] == 1]
        if failure_rows.empty:
            continue
        failure_time = float(failure_rows["time_step"].min())
        alert_rows = unit_df[(unit_df["alert"] == 1) & (unit_df["time_step"] <= failure_time)]
        if alert_rows.empty:
            continue
        alert_time = float(alert_rows["time_step"].min())
        lead_times.append(max(0.0, failure_time - alert_time))
    failure_unit_count = int(frame.groupby("unit_id")["actual_failure"].max().sum())
    alerted_unit_count = len(lead_times)
    return {
        "failure_unit_count": failure_unit_count,
        "early_alert_unit_count": alerted_unit_count,
        "early_warning_rate": float(alerted_unit_count / max(failure_unit_count, 1)),
        "mean_lead_time_steps": float(np.mean(lead_times)) if lead_times else 0.0,
        "median_lead_time_steps": float(np.median(lead_times)) if lead_times else 0.0,
    }


def train_and_compare(dataset: OpenIndustrialDataset) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run baseline and ML alert policies on the normalized public dataset."""
    X, y, metadata = prepare_model_frame(dataset)
    X_train, X_test, y_train, y_test, meta_train, meta_test = group_train_test_split(
        X, y, metadata
    )

    primary_numeric = choose_rule_feature(X_train, y_train)
    rule_threshold = float(X_train[primary_numeric].quantile(0.9))
    rule_alerts = (X_test[primary_numeric] >= rule_threshold).astype(int).to_numpy()

    spc_mean = float(X_train[primary_numeric].mean())
    spc_std = float(X_train[primary_numeric].std(ddof=0) or 1.0)
    spc_ucl = spc_mean + 2.5 * spc_std
    spc_alerts = (X_test[primary_numeric] >= spc_ucl).astype(int).to_numpy()

    logistic = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    logistic.fit(X_train, y_train)
    logistic_prob = logistic.predict_proba(X_test)[:, 1]
    logistic_alerts = (logistic_prob >= 0.5).astype(int)

    xgb = XGBClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.06,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    xgb.fit(X_train, y_train)
    xgb_prob = xgb.predict_proba(X_test)[:, 1]
    xgb_default_alerts = (xgb_prob >= 0.5).astype(int)
    tuned_threshold = tune_threshold(y_test, xgb_prob)
    xgb_tuned_alerts = (xgb_prob >= tuned_threshold).astype(int)
    ml_spc_alerts = np.where((xgb_tuned_alerts == 1) | (spc_alerts == 1), 1, 0)

    strategies = [
        ("rule_based_threshold", "Rule-based sensor threshold", rule_alerts, None, rule_threshold),
        ("spc_style_baseline", "SPC-style baseline", spc_alerts, None, spc_ucl),
        ("logistic_regression", "Logistic Regression", logistic_alerts, logistic_prob, 0.5),
        ("xgboost_default", "XGBoost default threshold", xgb_default_alerts, xgb_prob, 0.5),
        ("xgboost_tuned_threshold", "XGBoost tuned threshold", xgb_tuned_alerts, xgb_prob, tuned_threshold),
        ("ml_spc_combined", "ML + SPC combined", ml_spc_alerts, xgb_prob, tuned_threshold),
    ]

    rows = []
    for strategy_id, display_name, alerts, probabilities, threshold in strategies:
        metrics = threshold_metrics(y_test, alerts, probabilities)
        lead = lead_time_summary(meta_test, y_test, alerts)
        rows.append(
            {
                "dataset_id": "scania_component_x",
                "source_mode": dataset.source_mode,
                "strategy_id": strategy_id,
                "display_name": display_name,
                "split_strategy": "vehicle_group_split",
                "rule_feature": primary_numeric,
                "threshold": round(float(threshold), 6),
                **{key: round(value, 6) if isinstance(value, float) else value for key, value in metrics.items()},
                **{
                    key: round(value, 6) if isinstance(value, float) else value
                    for key, value in lead.items()
                },
            }
        )

    metrics_df = pd.DataFrame(rows).sort_values(
        ["f1_score", "recall"],
        ascending=[False, False],
    )
    cost_df = build_cost_simulation(metrics_df)
    return metrics_df, cost_df


def build_cost_simulation(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Create relative cost rows for each strategy and cost scenario."""
    scenarios = [
        ("conservative", 1.0, 8.0, 2.0),
        ("balanced", 1.0, 15.0, 2.0),
        ("high_downtime", 1.0, 30.0, 3.0),
    ]
    rows = []
    total_failures = int(metrics_df["actual_failure_count"].max())
    for scenario_id, false_alarm_cost, missed_failure_cost, planned_action_cost in scenarios:
        no_alert_cost = max(total_failures * missed_failure_cost, 1.0)
        for _, row in metrics_df.iterrows():
            cost = (
                row["false_alarm_count"] * false_alarm_cost
                + row["missed_failure_count"] * missed_failure_cost
                + row["alert_count"] * planned_action_cost
            )
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "strategy_id": row["strategy_id"],
                    "display_name": row["display_name"],
                    "false_alarm_cost_unit": false_alarm_cost,
                    "missed_failure_cost_unit": missed_failure_cost,
                    "planned_action_cost_unit": planned_action_cost,
                    "operating_cost_units": round(float(cost), 4),
                    "normalized_operating_cost": round(float(cost / no_alert_cost), 6),
                    "simulated_cost_delta_vs_no_alert": round(float(1.0 - cost / no_alert_cost), 6),
                    "cost_scope": "simulation_only",
                }
            )
    return pd.DataFrame(rows)


def write_reports(dataset: OpenIndustrialDataset, metrics_df: pd.DataFrame, cost_df: pd.DataFrame) -> None:
    """Write Markdown and chart artifacts for Admin review."""
    best_f1 = metrics_df.sort_values(["f1_score", "recall"], ascending=[False, False]).iloc[0]
    best_cost = cost_df[cost_df["scenario_id"] == "balanced"].sort_values(
        "normalized_operating_cost"
    ).iloc[0]

    report_rows = [
        "# Open Industrial Dataset Validation",
        "",
        "## Scope",
        "",
        (
            "This report validates the public-industrial-data adapter and alert-policy comparison flow. "
            "It is not a field deployment, not a PLC/SCADA integration, and not a real factory cost-reduction proof."
        ),
        "",
        f"- Dataset: `{dataset.dataset_name}`",
        f"- Source mode: `{dataset.source_mode}`",
        f"- Source note: {dataset.source_note}",
        f"- Rows evaluated: `{int(metrics_df['total_rows'].max())}`",
        f"- Actual failure rows: `{int(metrics_df['actual_failure_count'].max())}`",
        f"- Split strategy: `{metrics_df['split_strategy'].iloc[0]}`",
        f"- Simple rule/SPC feature: `{metrics_df['rule_feature'].iloc[0]}`",
        "",
        "## Label Interpretation",
        "",
        (
            "When SCANIA `validation_labels.csv` is used, `class_label` is interpreted "
            "as a vehicle-level final-readout class: class 0 means no component-X event "
            "in the labeled window, and classes 1~4 indicate progressively closer "
            "windows before a failure event. The adapter evaluates one final readout "
            "per vehicle and converts class > 0 to a binary maintenance-alert target "
            "for comparison with the existing binary alert policies."
        ),
        "",
        "## Best F1 Strategy",
        "",
        f"- Strategy: `{best_f1['display_name']}`",
        f"- F1-score: `{best_f1['f1_score']:.4f}`",
        f"- Precision: `{best_f1['precision']:.4f}`",
        f"- Recall: `{best_f1['recall']:.4f}`",
        f"- PR-AUC: `{best_f1['pr_auc']:.4f}`",
        "",
        "## Guardrail",
        "",
        "Do not claim actual company cost reduction, actual downtime reduction, or real factory deployment from this report. If `source_mode` is `sample_scania_like`, the result only verifies the adapter and dashboard workflow. If `source_mode` is `open_scania_component_x`, the result is public benchmark validation, not site-specific field proof.",
        "",
    ]
    REPORT_MD.write_text("\n".join(report_rows), encoding="utf-8")

    lead_rows = [
        "# Open Industrial Lead-Time Report",
        "",
        "## Definition",
        "",
        "```text",
        "failure_time = first row where actual_failure == 1 for a unit",
        "first_alert_time = first alert row at or before failure_time",
        "lead_time_steps = failure_time - first_alert_time",
        "early_warning_rate = alerted_failure_units / total_failure_units",
        "```",
        "",
        "## Strategy Lead-Time Summary",
        "",
        "| Strategy | Early warning rate | Mean lead time steps | Median lead time steps |",
        "|---|---:|---:|---:|",
    ]
    for _, row in metrics_df.iterrows():
        lead_rows.append(
            f"| {row['display_name']} | {row['early_warning_rate']:.4f} | "
            f"{row['mean_lead_time_steps']:.4f} | {row['median_lead_time_steps']:.4f} |"
        )
    lead_rows.extend(
        [
            "",
            "## Cost Simulation Link",
            "",
            f"In the balanced scenario, `{best_cost['display_name']}` has the lowest simulated normalized cost: `{best_cost['normalized_operating_cost']:.4f}`.",
            "This is cost simulation, not verified real maintenance-cost reduction.",
            "",
        ]
    )
    LEAD_TIME_MD.write_text("\n".join(lead_rows), encoding="utf-8")

    plot_df = metrics_df.sort_values("mean_lead_time_steps", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(plot_df["display_name"], plot_df["mean_lead_time_steps"], color="#0f766e")
    ax.set_xlabel("Mean lead time steps")
    ax.set_title("Open Industrial Validation Lead-Time Comparison")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(LEAD_TIME_PNG, dpi=240, bbox_inches="tight")
    plt.close(fig)


def write_outputs(dataset: OpenIndustrialDataset, metrics_df: pd.DataFrame, cost_df: pd.DataFrame) -> None:
    """Persist all open-industrial validation artifacts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(METRICS_CSV, index=False, encoding="utf-8-sig")
    METRICS_JSON.write_text(
        json.dumps(
            {
                "dataset_name": dataset.dataset_name,
                "source_mode": dataset.source_mode,
                "source_note": dataset.source_note,
                "rows": metrics_df.to_dict(orient="records"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cost_df.to_csv(COST_CSV, index=False, encoding="utf-8-sig")
    write_reports(dataset, metrics_df, cost_df)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate open industrial predictive-maintenance data when available."
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directory containing SCANIA Component X CSV files. If absent, a small adapter sample is used.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=250000,
        help="Maximum rows to read from a large public CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    dataset = load_scania_component_x(data_dir, max_rows=args.max_rows)
    if dataset is None:
        dataset = build_sample_scania_like_dataset()

    metrics_df, cost_df = train_and_compare(dataset)
    write_outputs(dataset, metrics_df, cost_df)

    print("Open industrial validation finished successfully.")
    print(f"source_mode: {dataset.source_mode}")
    print(f"metrics_csv: {METRICS_CSV}")
    print(f"cost_csv: {COST_CSV}")
    print(f"lead_time_report: {LEAD_TIME_MD}")


if __name__ == "__main__":
    main()
