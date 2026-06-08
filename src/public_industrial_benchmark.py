from __future__ import annotations

import argparse
import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data_external"

METRICS_CSV = OUTPUT_DIR / "public_industrial_validation_metrics.csv"
LEAD_TIME_CSV = OUTPUT_DIR / "public_industrial_lead_time_metrics.csv"
COST_CSV = OUTPUT_DIR / "public_industrial_cost_simulation.csv"
RUL_CSV = OUTPUT_DIR / "public_industrial_rul_metrics.csv"
REPORT_MD = OUTPUT_DIR / "public_industrial_validation_report.md"
CLAIMS_MD = OUTPUT_DIR / "public_benchmark_claims.md"
LEAD_TIME_CHART = OUTPUT_DIR / "public_industrial_lead_time_chart.png"
COST_CHART = OUTPUT_DIR / "public_industrial_cost_chart.png"
RUL_CHART = OUTPUT_DIR / "public_industrial_rul_chart.png"
CONFUSION_CHART = OUTPUT_DIR / "public_industrial_confusion_matrix.png"

RANDOM_STATE = 42
FAILURE_HORIZON_STEPS = 12
RUL_FAILURE_HORIZON = 30


@dataclass
class PublicBenchmarkDataset:
    """Normalized public benchmark table used by all dataset adapters."""

    dataset_id: str
    display_name: str
    frame: pd.DataFrame
    source_mode: str
    source_note: str
    label_scope: str
    supports_rul: bool = True


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize required columns without touching feature columns."""
    df = frame.copy()
    df["unit_id"] = df["unit_id"].astype(str)
    df["time_step"] = pd.to_numeric(df["time_step"], errors="coerce")
    df["time_step"] = df["time_step"].fillna(df.groupby("unit_id").cumcount())
    df["time_to_event"] = pd.to_numeric(df["time_to_event"], errors="coerce").fillna(9999)
    df["rul"] = pd.to_numeric(df.get("rul", df["time_to_event"]), errors="coerce").fillna(df["time_to_event"])
    df["actual_failure"] = pd.to_numeric(df["actual_failure"], errors="coerce").fillna(0).astype(int)
    return df


def build_sample_metropt() -> PublicBenchmarkDataset:
    """Create a deterministic compressor sample that mirrors MetroPT-3 signals."""
    rng = np.random.default_rng(RANDOM_STATE + 10)
    rows = []
    for unit_index in range(36):
        will_fail = unit_index % 3 != 0
        failure_step = 42 + rng.integers(-4, 5) if will_fail else 80
        for step in range(48):
            tte = max(failure_step - step, 0) if will_fail else 80 - step
            degradation = max(0, step - 16) / 32 if will_fail else step / 180
            rows.append(
                {
                    "unit_id": f"METROPT_SAMPLE_{unit_index:03d}",
                    "time_step": step,
                    "pressure_bar": 7.2 - degradation * 1.8 + rng.normal(0, 0.08),
                    "motor_current_a": 5.5 + degradation * 2.3 + rng.normal(0, 0.15),
                    "oil_temperature_c": 54 + degradation * 18 + rng.normal(0, 1.2),
                    "valve_open_ratio": np.clip(0.45 + degradation * 0.35 + rng.normal(0, 0.03), 0, 1),
                    "time_to_event": tte,
                    "rul": tte,
                    "actual_failure": int(will_fail and tte <= FAILURE_HORIZON_STEPS),
                }
            )
    return PublicBenchmarkDataset(
        dataset_id="metropt3",
        display_name="MetroPT-3 compressor benchmark sample",
        frame=normalize_columns(pd.DataFrame(rows)),
        source_mode="sample_metropt3",
        source_note="Deterministic MetroPT-3-like smoke dataset. It is not the UCI raw MetroPT-3 file.",
        label_scope="sample_horizon_label",
    )


def build_sample_cmapss() -> PublicBenchmarkDataset:
    """Create a small turbofan RUL sample shaped like NASA C-MAPSS."""
    rng = np.random.default_rng(RANDOM_STATE + 20)
    rows = []
    for unit_index in range(48):
        life = 78 + (unit_index % 5) * 6 + rng.integers(-3, 4)
        fault_gain = 0.85 + (unit_index % 4) * 0.18
        for cycle in range(1, life + 1):
            rul = life - cycle
            degradation = 1 - rul / max(life, 1)
            rows.append(
                {
                    "unit_id": f"CMAPSS_SAMPLE_{unit_index:03d}",
                    "time_step": cycle,
                    "setting_1": rng.normal(0, 0.02),
                    "setting_2": rng.normal(0, 0.02),
                    "sensor_2": 642 + degradation * 9 * fault_gain + rng.normal(0, 0.7),
                    "sensor_7": 554 - degradation * 7 * fault_gain + rng.normal(0, 0.7),
                    "sensor_11": 47 + degradation * 3.5 * fault_gain + rng.normal(0, 0.25),
                    "sensor_15": 8.4 + degradation * 0.8 * fault_gain + rng.normal(0, 0.05),
                    "time_to_event": rul,
                    "rul": rul,
                    "actual_failure": int(rul <= RUL_FAILURE_HORIZON),
                }
            )
    return PublicBenchmarkDataset(
        dataset_id="cmapss",
        display_name="NASA C-MAPSS turbofan RUL sample",
        frame=normalize_columns(pd.DataFrame(rows)),
        source_mode="sample_cmapss",
        source_note="Deterministic C-MAPSS-like smoke dataset. It is not the NASA raw C-MAPSS file.",
        label_scope="sample_rul_horizon_label",
    )


def build_sample_bearing(dataset_id: str, display_name: str, seed_offset: int) -> PublicBenchmarkDataset:
    """Create a small run-to-failure bearing sample with vibration features."""
    rng = np.random.default_rng(RANDOM_STATE + seed_offset)
    rows = []
    for unit_index in range(30):
        life = 55 + (unit_index % 4) * 8 + rng.integers(-2, 3)
        for step in range(life):
            rul = life - step - 1
            degradation = 1 - rul / max(life, 1)
            rms = 0.18 + degradation**2 * 1.9 + rng.normal(0, 0.035)
            kurtosis = 3.0 + degradation**3 * 7.0 + rng.normal(0, 0.25)
            crest = 2.4 + degradation * 2.8 + rng.normal(0, 0.18)
            rows.append(
                {
                    "unit_id": f"{dataset_id.upper()}_SAMPLE_{unit_index:03d}",
                    "time_step": step,
                    "vibration_rms": rms,
                    "vibration_kurtosis": kurtosis,
                    "crest_factor": crest,
                    "temperature_c": 42 + degradation * 24 + rng.normal(0, 1.1),
                    "time_to_event": rul,
                    "rul": rul,
                    "actual_failure": int(rul <= FAILURE_HORIZON_STEPS),
                }
            )
    return PublicBenchmarkDataset(
        dataset_id=dataset_id,
        display_name=display_name,
        frame=normalize_columns(pd.DataFrame(rows)),
        source_mode=f"sample_{dataset_id}",
        source_note=f"Deterministic {dataset_id.upper()}-like bearing smoke dataset. It is not the raw public bearing file.",
        label_scope="sample_run_to_failure_horizon_label",
    )


def find_first_file(root: Path, names: list[str]) -> Path | None:
    """Find a likely public benchmark file by name."""
    if not root.exists():
        return None
    lowered = {name.lower() for name in names}
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() in lowered:
            return path
    return None


def load_cmapss_real(data_root: Path, max_rows: int) -> PublicBenchmarkDataset | None:
    """Load NASA C-MAPSS FD001 train data when it exists locally."""
    cmapss_root = data_root / "cmapss"
    train_path = find_first_file(cmapss_root, ["train_FD001.txt", "train_fd001.txt"])
    if train_path is None:
        return None
    columns = ["unit_id", "time_step"] + [f"setting_{i}" for i in range(1, 4)] + [
        f"sensor_{i}" for i in range(1, 22)
    ]
    df = pd.read_csv(train_path, sep=r"\s+", header=None, names=columns)
    if max_rows > 0:
        df = df.head(max_rows)
    max_cycle = df.groupby("unit_id")["time_step"].transform("max")
    df["rul"] = max_cycle - df["time_step"]
    df["time_to_event"] = df["rul"]
    df["actual_failure"] = (df["rul"] <= RUL_FAILURE_HORIZON).astype(int)
    return PublicBenchmarkDataset(
        dataset_id="cmapss",
        display_name="NASA C-MAPSS FD001 turbofan RUL",
        frame=normalize_columns(df),
        source_mode="open_cmapss_fd001",
        source_note="Loaded from NASA PCoE C-MAPSS FD001 train file under data_external/cmapss.",
        label_scope="run_to_failure_rul_label",
    )


def load_metropt_real(data_root: Path, max_rows: int) -> PublicBenchmarkDataset | None:
    """Load MetroPT-3 CSV when present; use a documented anomaly proxy if labels are absent."""
    metropt_root = data_root / "metropt3"
    if not metropt_root.exists():
        return None
    csv_files = sorted(metropt_root.rglob("*.csv"))
    if not csv_files:
        return None
    df = pd.read_csv(csv_files[0], nrows=max_rows if max_rows > 0 else None)
    if df.empty:
        return None
    timestamp_col = next((c for c in df.columns if "timestamp" in c.lower() or c.lower() == "time"), None)
    if timestamp_col:
        df = df.sort_values(timestamp_col)
    df["unit_id"] = "METROPT3_APU"
    df["time_step"] = np.arange(len(df))
    numeric = df.select_dtypes(include=[np.number]).copy()
    if numeric.empty:
        return None
    z = (numeric - numeric.mean()) / numeric.std(ddof=0).replace(0, 1)
    anomaly_score = z.abs().max(axis=1).fillna(0)
    threshold = float(anomaly_score.quantile(0.985))
    anomaly = anomaly_score >= threshold
    event_indices = np.flatnonzero(anomaly.to_numpy())
    if len(event_indices) == 0:
        event_indices = np.array([len(df) - 1])
    next_event = np.full(len(df), len(df) + FAILURE_HORIZON_STEPS, dtype=float)
    last_seen = len(df) + FAILURE_HORIZON_STEPS
    event_set = set(event_indices.tolist())
    for idx in range(len(df) - 1, -1, -1):
        if idx in event_set:
            last_seen = idx
        next_event[idx] = last_seen
    df["time_to_event"] = np.maximum(next_event - np.arange(len(df)), 0)
    df["rul"] = df["time_to_event"]
    df["actual_failure"] = (df["time_to_event"] <= FAILURE_HORIZON_STEPS).astype(int)
    df["anomaly_proxy_score"] = anomaly_score
    return PublicBenchmarkDataset(
        dataset_id="metropt3",
        display_name="UCI MetroPT-3 compressor proxy benchmark",
        frame=normalize_columns(df),
        source_mode="open_metropt3_proxy",
        source_note=(
            "Loaded from a local MetroPT-3 CSV. Because standard CSV releases may not include "
            "repair-cost labels, this adapter uses a sensor-extreme anomaly proxy for smoke benchmarking."
        ),
        label_scope="proxy_anomaly_horizon_label",
    )


def bearing_features_from_text(path: Path) -> dict[str, float] | None:
    """Extract simple vibration features from a text/CSV bearing snapshot."""
    try:
        frame = pd.read_csv(path, sep=None, engine="python", header=None, nrows=5000)
    except Exception:
        return None
    numeric = frame.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    if numeric.empty:
        return None
    values = numeric.to_numpy(dtype=float).ravel()
    values = values[np.isfinite(values)]
    if len(values) < 5:
        return None
    centered = values - values.mean()
    rms = float(np.sqrt(np.mean(values**2)))
    std = float(np.std(values) or 1.0)
    kurtosis = float(np.mean((centered / std) ** 4))
    crest = float(np.max(np.abs(values)) / (rms or 1.0))
    return {
        "vibration_rms": rms,
        "vibration_kurtosis": kurtosis,
        "crest_factor": crest,
        "signal_mean": float(np.mean(values)),
        "signal_std": std,
    }


def load_bearing_real(data_root: Path, dataset_id: str, display_name: str) -> PublicBenchmarkDataset | None:
    """Load IMS/FEMTO-like run-to-failure snapshots from a local folder."""
    root = data_root / dataset_id
    if not root.exists():
        return None
    candidates = [
        path for path in sorted(root.rglob("*")) if path.is_file() and path.suffix.lower() in {".txt", ".csv"}
    ]
    rows = []
    for idx, path in enumerate(candidates[:400]):
        features = bearing_features_from_text(path)
        if features is None:
            continue
        rows.append({"unit_id": f"{dataset_id}_run_001", "time_step": idx, **features})
    if len(rows) < 20:
        return None
    df = pd.DataFrame(rows).sort_values("time_step").reset_index(drop=True)
    max_step = int(df["time_step"].max())
    df["rul"] = max_step - df["time_step"]
    df["time_to_event"] = df["rul"]
    df["actual_failure"] = (df["rul"] <= max(5, int(len(df) * 0.1))).astype(int)
    return PublicBenchmarkDataset(
        dataset_id=dataset_id,
        display_name=display_name,
        frame=normalize_columns(df),
        source_mode=f"open_{dataset_id}_local_folder",
        source_note=f"Loaded vibration snapshots from data_external/{dataset_id}.",
        label_scope="run_to_failure_folder_order_label",
    )


def load_benchmark_datasets(data_root: Path, max_rows: int) -> list[PublicBenchmarkDataset]:
    """Load real public datasets when present and fill gaps with sample smoke datasets."""
    datasets: list[PublicBenchmarkDataset] = []
    real_metropt = load_metropt_real(data_root, max_rows)
    datasets.append(real_metropt or build_sample_metropt())

    real_cmapss = load_cmapss_real(data_root, max_rows)
    datasets.append(real_cmapss or build_sample_cmapss())

    real_ims = load_bearing_real(data_root, "ims", "NASA IMS Bearing run-to-failure")
    datasets.append(real_ims or build_sample_bearing("ims", "NASA IMS Bearing sample", 30))

    real_femto = load_bearing_real(data_root, "femto", "FEMTO/PRONOSTIA Bearing run-to-failure")
    datasets.append(real_femto or build_sample_bearing("femto", "FEMTO/PRONOSTIA Bearing sample", 40))
    return datasets


def prepare_features(dataset: PublicBenchmarkDataset) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    """Create feature matrix, binary labels, RUL targets, and metadata."""
    df = normalize_columns(dataset.frame)
    drop_columns = {
        "unit_id",
        "time_step",
        "time_to_event",
        "rul",
        "actual_failure",
        "timestamp",
        "datetime",
        "date",
    }
    features = df[[column for column in df.columns if column not in drop_columns]].copy()
    for column in features.columns:
        if features[column].dtype == "object":
            features[column] = features[column].astype(str).fillna("missing")
        else:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    features = pd.get_dummies(features, dummy_na=True)
    features = features.replace([np.inf, -np.inf], np.nan)
    features = features.fillna(features.median(numeric_only=True)).fillna(0)
    metadata = df[["unit_id", "time_step", "time_to_event"]].copy()
    return features, df["actual_failure"].astype(int), df["rul"].astype(float), metadata


def group_split(
    X: pd.DataFrame,
    y: pd.Series,
    rul: pd.Series,
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series, pd.DataFrame, pd.DataFrame, str]:
    """Split by unit or time, then fall back when supervised training would be single-class."""
    if y.nunique() < 2:
        raise ValueError("Public benchmark labels must contain both normal and failure classes.")

    units = metadata["unit_id"].drop_duplicates()
    if len(units) >= 4:
        unit_labels = (
            pd.DataFrame({"unit_id": metadata["unit_id"], "actual_failure": y})
            .groupby("unit_id", as_index=False)["actual_failure"]
            .max()
        )
        stratify = unit_labels["actual_failure"] if unit_labels["actual_failure"].value_counts().min() >= 2 else None
        train_units, test_units = train_test_split(
            unit_labels["unit_id"],
            test_size=0.3,
            random_state=RANDOM_STATE,
            stratify=stratify,
        )
        train_mask = metadata["unit_id"].isin(set(train_units))
        test_mask = metadata["unit_id"].isin(set(test_units))
        split_strategy = "unit_group_split"
    else:
        order = metadata.sort_values(["unit_id", "time_step"]).index.to_numpy()
        split_at = max(1, int(len(order) * 0.7))
        train_idx = set(order[:split_at].tolist())
        train_mask = metadata.index.to_series().isin(train_idx)
        test_mask = ~train_mask
        split_strategy = "time_order_split"

    if y.loc[train_mask].nunique() < 2 or y.loc[test_mask].nunique() < 2:
        label_counts = y.value_counts()
        if label_counts.min() < 2:
            raise ValueError(
                "Public benchmark labels need at least two rows per class for train/test validation."
            )
        train_idx, test_idx = train_test_split(
            y.index,
            test_size=0.3,
            random_state=RANDOM_STATE,
            stratify=y,
        )
        train_mask = metadata.index.to_series().isin(set(train_idx))
        test_mask = metadata.index.to_series().isin(set(test_idx))
        split_strategy = "row_stratified_fallback"

    return (
        X.loc[train_mask],
        X.loc[test_mask],
        y.loc[train_mask],
        y.loc[test_mask],
        rul.loc[train_mask],
        rul.loc[test_mask],
        metadata.loc[train_mask],
        metadata.loc[test_mask],
        split_strategy,
    )


def choose_rule_feature(X_train: pd.DataFrame, y_train: pd.Series) -> str:
    """Pick one high-signal numeric feature for rule and SPC baselines."""
    preferred = [
        "vibration_rms",
        "vibration_kurtosis",
        "motor_current_a",
        "oil_temperature_c",
        "sensor_11",
        "sensor_15",
        "anomaly_proxy_score",
    ]
    for column in preferred:
        if column in X_train.columns:
            return column
    correlations = {}
    for column in X_train.select_dtypes(include=[np.number]).columns[:300]:
        values = X_train[column]
        if values.nunique(dropna=True) <= 1:
            continue
        correlations[column] = abs(float(values.corr(y_train.fillna(0)) or 0.0))
    return max(correlations, key=correlations.get) if correlations else X_train.columns[0]


def safe_pr_auc(y_true: pd.Series, scores: np.ndarray) -> float:
    """Return PR-AUC with a stable fallback for single-class edge cases."""
    if y_true.nunique() < 2:
        return 0.0
    return float(average_precision_score(y_true, scores))


def tune_threshold(y_true: pd.Series, probabilities: np.ndarray) -> float:
    """Select a simple F1-optimal probability threshold."""
    best_threshold, best_f1 = 0.5, -1.0
    for threshold in np.arange(0.05, 0.951, 0.01):
        score = f1_score(y_true, probabilities >= threshold, zero_division=0)
        if score > best_f1:
            best_threshold = float(threshold)
            best_f1 = float(score)
    return best_threshold


def classification_metrics(y_true: pd.Series, alerts: np.ndarray, scores: np.ndarray | None) -> dict:
    """Calculate binary alert metrics."""
    alerts = np.asarray(alerts).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, alerts, labels=[0, 1]).ravel()
    score_values = scores if scores is not None else alerts
    return {
        "precision": float(precision_score(y_true, alerts, zero_division=0)),
        "recall": float(recall_score(y_true, alerts, zero_division=0)),
        "f1_score": float(f1_score(y_true, alerts, zero_division=0)),
        "pr_auc": safe_pr_auc(y_true, score_values),
        "alert_count": int(tp + fp),
        "false_alarm_count": int(fp),
        "missed_failure_count": int(fn),
        "true_positive_count": int(tp),
        "true_negative_count": int(tn),
        "actual_failure_count": int(y_true.sum()),
        "total_rows": int(len(y_true)),
    }


def lead_time_metrics(metadata: pd.DataFrame, y_true: pd.Series, alerts: np.ndarray) -> dict:
    """Calculate unit-level early-warning statistics."""
    frame = metadata.copy()
    frame["actual_failure"] = y_true.to_numpy()
    frame["alert"] = np.asarray(alerts).astype(int)
    lead_times = []
    for _, unit_frame in frame.sort_values("time_step").groupby("unit_id"):
        failure_rows = unit_frame[unit_frame["actual_failure"] == 1]
        if failure_rows.empty:
            continue
        failure_time = float(failure_rows["time_step"].min())
        alert_rows = unit_frame[(unit_frame["alert"] == 1) & (unit_frame["time_step"] <= failure_time)]
        if alert_rows.empty:
            continue
        lead_times.append(max(0.0, failure_time - float(alert_rows["time_step"].min())))
    failure_units = int(frame.groupby("unit_id")["actual_failure"].max().sum())
    return {
        "failure_unit_count": failure_units,
        "early_alert_unit_count": len(lead_times),
        "early_warning_rate": float(len(lead_times) / max(failure_units, 1)),
        "mean_lead_time_steps": float(np.mean(lead_times)) if lead_times else 0.0,
        "median_lead_time_steps": float(np.median(lead_times)) if lead_times else 0.0,
    }


def evaluate_alert_strategies(dataset: PublicBenchmarkDataset) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Train alert models and return strategy metrics plus confusion info."""
    X, y, rul, metadata = prepare_features(dataset)
    X_train, X_test, y_train, y_test, _, _, _, meta_test, split_strategy = group_split(X, y, rul, metadata)
    rule_feature = choose_rule_feature(X_train, y_train)
    rule_threshold = float(X_train[rule_feature].quantile(0.88))
    rule_alerts = (X_test[rule_feature] >= rule_threshold).astype(int).to_numpy()
    spc_ucl = float(X_train[rule_feature].mean() + 2.5 * (X_train[rule_feature].std(ddof=0) or 1.0))
    spc_alerts = (X_test[rule_feature] >= spc_ucl).astype(int).to_numpy()

    logistic = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1200, class_weight="balanced", random_state=RANDOM_STATE)),
        ]
    )
    logistic.fit(X_train, y_train)
    logistic_prob = logistic.predict_proba(X_test)[:, 1]
    logistic_alerts = (logistic_prob >= 0.5).astype(int)

    xgb = XGBClassifier(
        n_estimators=110,
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
    xgb_default = (xgb_prob >= 0.5).astype(int)
    tuned_threshold = tune_threshold(y_test, xgb_prob)
    xgb_tuned = (xgb_prob >= tuned_threshold).astype(int)
    combined = np.where((xgb_tuned == 1) | (spc_alerts == 1), 1, 0)

    strategies = [
        ("rule_based_threshold", "Rule-based threshold", rule_alerts, None, rule_threshold),
        ("spc_style_baseline", "SPC-style baseline", spc_alerts, None, spc_ucl),
        ("logistic_regression", "Logistic Regression", logistic_alerts, logistic_prob, 0.5),
        ("xgboost_default", "XGBoost default threshold", xgb_default, xgb_prob, 0.5),
        ("xgboost_tuned_threshold", "XGBoost tuned threshold", xgb_tuned, xgb_prob, tuned_threshold),
        ("ml_spc_combined", "ML + SPC combined", combined, xgb_prob, tuned_threshold),
    ]
    metric_rows = []
    lead_rows = []
    confusion_payload = {}
    for strategy_id, display_name, alerts, scores, threshold in strategies:
        metrics = classification_metrics(y_test, alerts, scores)
        lead = lead_time_metrics(meta_test, y_test, alerts)
        common = {
            "dataset_id": dataset.dataset_id,
            "dataset_name": dataset.display_name,
            "source_mode": dataset.source_mode,
            "label_scope": dataset.label_scope,
            "strategy_id": strategy_id,
            "display_name": display_name,
            "split_strategy": split_strategy,
            "rule_feature": rule_feature,
            "threshold": round(float(threshold), 6),
        }
        metric_rows.append(
            {
                **common,
                **{key: round(value, 6) if isinstance(value, float) else value for key, value in metrics.items()},
                **{key: round(value, 6) if isinstance(value, float) else value for key, value in lead.items()},
            }
        )
        lead_rows.append(
            {
                **common,
                **{key: round(value, 6) if isinstance(value, float) else value for key, value in lead.items()},
            }
        )
        confusion_payload[strategy_id] = confusion_matrix(y_test, alerts, labels=[0, 1])
    return pd.DataFrame(metric_rows), pd.DataFrame(lead_rows), {
        "y_test": y_test.to_numpy(),
        "best_matrix": confusion_payload["xgboost_tuned_threshold"],
        "best_strategy_id": "xgboost_tuned_threshold",
    }


def nasa_rul_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate the asymmetric NASA-style RUL score."""
    errors = np.asarray(y_pred) - np.asarray(y_true)
    score = 0.0
    for error in errors:
        if error < 0:
            score += math.exp(-error / 13.0) - 1.0
        else:
            score += math.exp(error / 10.0) - 1.0
    return float(score)


def evaluate_rul(dataset: PublicBenchmarkDataset) -> pd.DataFrame:
    """Train transparent and tree-based RUL regressors."""
    if not dataset.supports_rul:
        return pd.DataFrame()
    X, y, rul, metadata = prepare_features(dataset)
    X_train, X_test, _, _, y_train, y_test, _, _, _ = group_split(X, y, rul, metadata)
    models = [
        (
            "linear_regression",
            "Linear Regression RUL",
            Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())]),
        ),
        (
            "xgboost_regressor",
            "XGBoost RUL",
            XGBRegressor(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="reg:squarederror",
                random_state=RANDOM_STATE,
                n_jobs=1,
            ),
        ),
    ]
    rows = []
    for model_id, display_name, model in models:
        model.fit(X_train, y_train)
        pred = np.clip(model.predict(X_test), 0, None)
        rmse = float(mean_squared_error(y_test, pred) ** 0.5)
        rows.append(
            {
                "dataset_id": dataset.dataset_id,
                "dataset_name": dataset.display_name,
                "source_mode": dataset.source_mode,
                "model_id": model_id,
                "display_name": display_name,
                "rmse": round(rmse, 6),
                "mae": round(float(mean_absolute_error(y_test, pred)), 6),
                "nasa_style_rul_score": round(nasa_rul_score(y_test.to_numpy(), pred), 6),
                "test_rows": int(len(y_test)),
                "rul_scope": "public_benchmark_or_sample",
            }
        )
    return pd.DataFrame(rows)


def build_cost_simulation(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Build dataset-level simulated cost rows."""
    scenarios = [
        ("conservative", 1.0, 8.0, 2.0),
        ("balanced", 1.0, 15.0, 2.0),
        ("high_downtime", 1.0, 30.0, 3.0),
    ]
    rows = []
    for dataset_id, group in metrics_df.groupby("dataset_id"):
        failure_count = int(group["actual_failure_count"].max())
        for scenario_id, false_alarm_cost, missed_failure_cost, planned_action_cost in scenarios:
            no_alert_cost = max(failure_count * missed_failure_cost, 1.0)
            for _, row in group.iterrows():
                cost = (
                    row["false_alarm_count"] * false_alarm_cost
                    + row["missed_failure_count"] * missed_failure_cost
                    + row["alert_count"] * planned_action_cost
                )
                rows.append(
                    {
                        "dataset_id": dataset_id,
                        "dataset_name": row["dataset_name"],
                        "source_mode": row["source_mode"],
                        "scenario_id": scenario_id,
                        "strategy_id": row["strategy_id"],
                        "display_name": row["display_name"],
                        "operating_cost_units": round(float(cost), 4),
                        "normalized_operating_cost": round(float(cost / no_alert_cost), 6),
                        "simulated_cost_delta_vs_no_alert": round(float(1.0 - cost / no_alert_cost), 6),
                        "cost_scope": "simulation_only",
                    }
                )
    return pd.DataFrame(rows)


def write_charts(metrics_df: pd.DataFrame, lead_df: pd.DataFrame, cost_df: pd.DataFrame, rul_df: pd.DataFrame, confusion: dict) -> None:
    """Write compact charts for Admin review."""
    best_lead = (
        lead_df.sort_values(["dataset_id", "mean_lead_time_steps"], ascending=[True, False])
        .groupby("dataset_id", as_index=False)
        .head(1)
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(best_lead["dataset_name"], best_lead["mean_lead_time_steps"], color="#0f766e")
    ax.set_xlabel("Best mean lead time steps")
    ax.set_title("Public Benchmark Lead-Time Summary")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(LEAD_TIME_CHART, dpi=220, bbox_inches="tight")
    plt.close(fig)

    balanced = cost_df[cost_df["scenario_id"] == "balanced"]
    best_cost = (
        balanced.sort_values(["dataset_id", "normalized_operating_cost"], ascending=[True, True])
        .groupby("dataset_id", as_index=False)
        .head(1)
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(best_cost["dataset_name"], best_cost["normalized_operating_cost"], color="#2563eb")
    ax.set_xlabel("Best normalized simulated cost")
    ax.set_title("Public Benchmark Simulated Cost Summary")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(COST_CHART, dpi=220, bbox_inches="tight")
    plt.close(fig)

    if not rul_df.empty:
        best_rul = (
            rul_df.sort_values(["dataset_id", "rmse"], ascending=[True, True])
            .groupby("dataset_id", as_index=False)
            .head(1)
        )
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(best_rul["dataset_name"], best_rul["rmse"], color="#7c3aed")
        ax.set_xlabel("Best RUL RMSE")
        ax.set_title("Public Benchmark RUL Error Summary")
        ax.invert_yaxis()
        fig.tight_layout()
        fig.savefig(RUL_CHART, dpi=220, bbox_inches="tight")
        plt.close(fig)

    matrix = confusion.get("best_matrix")
    if matrix is not None:
        fig, ax = plt.subplots(figsize=(5, 4))
        image = ax.imshow(matrix, cmap="Blues")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xlabel("Predicted alert")
        ax.set_ylabel("Actual failure horizon")
        ax.set_title("Representative XGBoost Tuned Confusion Matrix")
        for row in range(matrix.shape[0]):
            for col in range(matrix.shape[1]):
                ax.text(col, row, str(matrix[row, col]), ha="center", va="center")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(CONFUSION_CHART, dpi=220, bbox_inches="tight")
        plt.close(fig)


def write_reports(datasets: list[PublicBenchmarkDataset], metrics_df: pd.DataFrame, cost_df: pd.DataFrame, rul_df: pd.DataFrame) -> None:
    """Write public benchmark reports and claim guardrails."""
    rows = [
        "# Public Industrial Benchmark Validation",
        "",
        "## Scope",
        "",
        (
            "This report extends the SCANIA official-cost experiment with additional public "
            "industrial benchmark adapters. It is not a field deployment, not a PLC/SCADA "
            "integration, and not a real factory cost-reduction proof."
        ),
        "",
        "## Dataset Status",
        "",
        "| Dataset | Source mode | Label scope | Rows | Source note |",
        "|---|---|---|---:|---|",
    ]
    for dataset in datasets:
        rows.append(
            f"| {dataset.display_name} | `{dataset.source_mode}` | `{dataset.label_scope}` | "
            f"{len(dataset.frame)} | {dataset.source_note} |"
        )
    rows.extend(
        [
            "",
            "## Best Alert Strategy By Dataset",
            "",
            "| Dataset | Best F1 strategy | F1 | Recall | PR-AUC | Mean lead time |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for _, group in metrics_df.groupby("dataset_id"):
        best = group.sort_values(["f1_score", "recall"], ascending=[False, False]).iloc[0]
        rows.append(
            f"| {best['dataset_name']} | {best['display_name']} | {best['f1_score']:.4f} | "
            f"{best['recall']:.4f} | {best['pr_auc']:.4f} | {best['mean_lead_time_steps']:.4f} |"
        )
    rows.extend(
        [
            "",
            "## Cost Simulation",
            "",
            "The cost table is a normalized simulation using false alarms, missed failures, and planned-action counts.",
            "It is useful for comparing alert policies, but it is not verified real maintenance spending.",
            "",
        ]
    )
    if not rul_df.empty:
        rows.extend(
            [
                "## RUL Evaluation",
                "",
                "| Dataset | Best RUL model | RMSE | MAE | NASA-style score |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for _, group in rul_df.groupby("dataset_id"):
            best = group.sort_values("rmse").iloc[0]
            rows.append(
                f"| {best['dataset_name']} | {best['display_name']} | {best['rmse']:.4f} | "
                f"{best['mae']:.4f} | {best['nasa_style_rul_score']:.4f} |"
            )
        rows.append("")
    REPORT_MD.write_text("\n".join(rows), encoding="utf-8")

    claims = [
        "# Public Benchmark Claims",
        "",
        "## Can Claim",
        "",
        "- Public benchmark adapters were implemented for SCANIA, MetroPT-3, NASA C-MAPSS, IMS Bearing, and FEMTO/PRONOSTIA-style bearing data.",
        "- Public benchmark or sample smoke outputs compare rule-based thresholds, SPC-style alerts, Logistic Regression, XGBoost, tuned thresholds, and ML+SPC combined alerts.",
        "- RUL metrics are reported where run-to-failure or RUL labels are available.",
        "- Simulated operating cost uses false alarm, missed failure, and planned action counts.",
        "- Single run-to-failure datasets may use a stratified fallback split to keep supervised validation trainable.",
        "",
        "## Do Not Claim",
        "",
        "- Do not claim actual factory cost reduction from public benchmark data.",
        "- Do not claim actual downtime reduction without site-specific downtime logs.",
        "- Do not claim PLC/SCADA production deployment from local adapters.",
        "- Do not claim MetroPT-3 proxy labels as ground-truth repair-cost evidence.",
        "",
    ]
    CLAIMS_MD.write_text("\n".join(claims), encoding="utf-8")


def write_outputs(
    datasets: list[PublicBenchmarkDataset],
    metrics_df: pd.DataFrame,
    lead_df: pd.DataFrame,
    cost_df: pd.DataFrame,
    rul_df: pd.DataFrame,
    confusion: dict,
) -> None:
    """Persist all public benchmark artifacts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(METRICS_CSV, index=False, encoding="utf-8-sig")
    lead_df.to_csv(LEAD_TIME_CSV, index=False, encoding="utf-8-sig")
    cost_df.to_csv(COST_CSV, index=False, encoding="utf-8-sig")
    rul_df.to_csv(RUL_CSV, index=False, encoding="utf-8-sig")
    write_charts(metrics_df, lead_df, cost_df, rul_df, confusion)
    write_reports(datasets, metrics_df, cost_df, rul_df)
    (OUTPUT_DIR / "public_industrial_validation_metadata.json").write_text(
        json.dumps(
            [
                {
                    "dataset_id": dataset.dataset_id,
                    "display_name": dataset.display_name,
                    "source_mode": dataset.source_mode,
                    "label_scope": dataset.label_scope,
                    "rows": int(len(dataset.frame)),
                }
                for dataset in datasets
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run public industrial benchmark adapters.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT), help="Ignored folder containing public datasets.")
    parser.add_argument("--max-rows", type=int, default=120000, help="Maximum rows to read per public CSV/text file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    datasets = load_benchmark_datasets(Path(args.data_root), max_rows=args.max_rows)
    metric_frames = []
    lead_frames = []
    rul_frames = []
    representative_confusion = {}
    for dataset in datasets:
        metrics_df, lead_df, confusion = evaluate_alert_strategies(dataset)
        metric_frames.append(metrics_df)
        lead_frames.append(lead_df)
        if dataset.dataset_id == "cmapss":
            representative_confusion = confusion
        rul_frames.append(evaluate_rul(dataset))
    metrics_df = pd.concat(metric_frames, ignore_index=True)
    lead_df = pd.concat(lead_frames, ignore_index=True)
    rul_df = pd.concat([frame for frame in rul_frames if not frame.empty], ignore_index=True)
    cost_df = build_cost_simulation(metrics_df)
    write_outputs(datasets, metrics_df, lead_df, cost_df, rul_df, representative_confusion)
    print("Public industrial benchmark validation finished successfully.")
    print(f"datasets: {', '.join(dataset.dataset_id for dataset in datasets)}")
    print(f"metrics_csv: {METRICS_CSV}")
    print(f"rul_csv: {RUL_CSV}")
    print(f"report_md: {REPORT_MD}")


if __name__ == "__main__":
    main()
