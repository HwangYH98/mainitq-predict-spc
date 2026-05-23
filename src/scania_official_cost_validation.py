from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data_external" / "scania_component_x"

METRICS_CSV = OUTPUT_DIR / "scania_official_cost_metrics.csv"
METRICS_JSON = OUTPUT_DIR / "scania_official_cost_metrics.json"
PREDICTIONS_CSV = OUTPUT_DIR / "scania_official_predictions.csv"
REPORT_MD = OUTPUT_DIR / "scania_official_cost_report.md"
COST_CHART = OUTPUT_DIR / "scania_official_cost_comparison.png"
CONFUSION_CHART = OUTPUT_DIR / "scania_official_confusion_matrix.png"
MODEL_ARTIFACT = OUTPUT_DIR / "scania_cost_optimized_model.joblib"

RANDOM_STATE = 42
CLASSES = [0, 1, 2, 3, 4]
CLASS_WINDOWS = {
    0: "outside failure window or no repair",
    1: "48~24 time units before failure",
    2: "24~12 time units before failure",
    3: "12~6 time units before failure",
    4: "6~0 time units before failure",
}

# Rows are actual class, columns are predicted class. The values follow the
# SCANIA Component X / IDA challenge official misclassification-cost table.
OFFICIAL_COST_MATRIX = np.array(
    [
        [0, 7, 8, 9, 10],
        [200, 0, 7, 8, 9],
        [300, 200, 0, 7, 8],
        [400, 300, 200, 0, 7],
        [500, 400, 300, 200, 0],
    ],
    dtype=float,
)


@dataclass
class ScaniaOfficialData:
    """Prepared train/validation data for the official class-cost task."""

    train: pd.DataFrame
    validation: pd.DataFrame
    source_note: str


def required_files(data_dir: Path) -> list[Path]:
    """Return the files needed for the official SCANIA class-cost experiment."""
    return [
        data_dir / "train_operational_readouts.csv",
        data_dir / "train_tte.csv",
        data_dir / "train_specifications.csv",
        data_dir / "validation_operational_readouts.csv",
        data_dir / "validation_labels.csv",
        data_dir / "validation_specifications.csv",
    ]


def assert_required_files(data_dir: Path) -> None:
    """Fail with a friendly message when large public data is missing."""
    missing = [path.name for path in required_files(data_dir) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing SCANIA official files: "
            + ", ".join(missing)
            + ". Run: .\\.venv\\Scripts\\python.exe src\\download_scania_component_x.py --include-train --skip-docs"
        )


def class_from_time_to_event(time_to_event: pd.Series, repaired: pd.Series) -> pd.Series:
    """Map SCANIA time-to-event values into official classes 0~4."""
    tte = pd.to_numeric(time_to_event, errors="coerce")
    is_repaired = repaired.fillna(0).astype(int) == 1
    label = pd.Series(0, index=tte.index, dtype="int64")
    label[is_repaired & (tte > 24) & (tte <= 48)] = 1
    label[is_repaired & (tte > 12) & (tte <= 24)] = 2
    label[is_repaired & (tte > 6) & (tte <= 12)] = 3
    label[is_repaired & (tte >= 0) & (tte <= 6)] = 4
    return label


def attach_specs(frame: pd.DataFrame, specs: pd.DataFrame) -> pd.DataFrame:
    """Attach vehicle-level specifications to readout rows."""
    spec_columns = [column for column in specs.columns if column != "vehicle_id"]
    if not spec_columns:
        return frame
    return frame.merge(specs, on="vehicle_id", how="left")


def load_training_sample(
    data_dir: Path,
    max_rows_per_class: int,
    chunk_size: int,
) -> pd.DataFrame:
    """Read the large training CSV once and keep a balanced class sample."""
    tte = pd.read_csv(data_dir / "train_tte.csv")
    specs = pd.read_csv(data_dir / "train_specifications.csv")
    collected: dict[int, list[pd.DataFrame]] = {class_id: [] for class_id in CLASSES}
    remaining = {class_id: max_rows_per_class for class_id in CLASSES}

    for chunk in pd.read_csv(data_dir / "train_operational_readouts.csv", chunksize=chunk_size):
        chunk = chunk.merge(tte, on="vehicle_id", how="left").copy()
        time_to_event = chunk["length_of_study_time_step"] - chunk["time_step"]
        chunk = chunk.assign(
            time_to_event=time_to_event,
            class_label=class_from_time_to_event(time_to_event, chunk["in_study_repair"]),
        )
        chunk = attach_specs(chunk, specs)

        for class_id in CLASSES:
            need = remaining[class_id]
            if need <= 0:
                continue
            subset = chunk[chunk["class_label"] == class_id]
            if subset.empty:
                continue
            take = min(need, len(subset))
            if len(subset) > take:
                subset = subset.sample(n=take, random_state=RANDOM_STATE + class_id)
            collected[class_id].append(subset)
            remaining[class_id] -= take

        if all(value <= 0 for value in remaining.values()):
            break

    frames = [part for class_parts in collected.values() for part in class_parts]
    if not frames:
        raise RuntimeError("No SCANIA training rows were collected.")
    train = pd.concat(frames, ignore_index=True)
    missing_classes = sorted(set(CLASSES) - set(train["class_label"].unique().tolist()))
    if missing_classes:
        raise RuntimeError(f"Training sample is missing official classes: {missing_classes}")
    return train.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)


def load_validation_final_readouts(data_dir: Path) -> pd.DataFrame:
    """Load one final readout per validation vehicle and attach official labels."""
    operational = pd.read_csv(data_dir / "validation_operational_readouts.csv")
    labels = pd.read_csv(data_dir / "validation_labels.csv")
    specs = pd.read_csv(data_dir / "validation_specifications.csv")
    final_rows = (
        operational.sort_values(["vehicle_id", "time_step"])
        .groupby("vehicle_id", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )
    final_rows = final_rows.merge(labels, on="vehicle_id", how="inner")
    final_rows = attach_specs(final_rows, specs)
    final_rows["class_label"] = pd.to_numeric(final_rows["class_label"], errors="raise").astype(int)
    return final_rows


def load_scania_official_data(
    data_dir: Path,
    max_rows_per_class: int,
    chunk_size: int,
) -> ScaniaOfficialData:
    """Load train and validation tables for the official cost metric task."""
    assert_required_files(data_dir)
    train = load_training_sample(data_dir, max_rows_per_class=max_rows_per_class, chunk_size=chunk_size)
    validation = load_validation_final_readouts(data_dir)
    return ScaniaOfficialData(
        train=train,
        validation=validation,
        source_note=(
            "SCANIA Component X public dataset from Researchdata.se "
            "(DOI: 10.58141/1w9m-yz81, CC BY 4.0)."
        ),
    )


def prepare_features(
    train: pd.DataFrame,
    validation: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, list[str], list[str], list[str]]:
    """Create aligned one-hot feature matrices for train and validation."""
    drop_columns = {
        "vehicle_id",
        "time_step",
        "class_label",
        "length_of_study_time_step",
        "in_study_repair",
        "time_to_event",
    }
    feature_columns = [column for column in train.columns if column not in drop_columns]
    train_features = train[feature_columns].copy()
    validation_features = validation[[column for column in feature_columns if column in validation.columns]].copy()
    for column in feature_columns:
        if column not in validation_features.columns:
            validation_features[column] = np.nan
    validation_features = validation_features[feature_columns]

    combined = pd.concat(
        [train_features.assign(__split="train"), validation_features.assign(__split="validation")],
        ignore_index=True,
    )
    categorical_columns: list[str] = []
    for column in feature_columns:
        if combined[column].dtype == "object":
            categorical_columns.append(column)
            combined[column] = combined[column].astype(str).fillna("missing")
        else:
            combined[column] = pd.to_numeric(combined[column], errors="coerce")
    combined = pd.get_dummies(combined, columns=[c for c in feature_columns if combined[c].dtype == "object"], dummy_na=True)
    split = combined.pop("__split")
    combined = combined.replace([np.inf, -np.inf], np.nan)
    combined = combined.fillna(combined.median(numeric_only=True)).fillna(0)

    X_train = combined[split == "train"].reset_index(drop=True)
    X_validation = combined[split == "validation"].reset_index(drop=True)
    y_train = train["class_label"].astype(int).reset_index(drop=True)
    y_validation = validation["class_label"].astype(int).reset_index(drop=True)
    return X_train, X_validation, y_train, y_validation, X_train.columns.tolist(), feature_columns, categorical_columns


def official_cost(y_true: pd.Series | np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate the official SCANIA misclassification cost."""
    true_values = np.asarray(y_true, dtype=int)
    pred_values = np.asarray(y_pred, dtype=int)
    return float(OFFICIAL_COST_MATRIX[true_values, pred_values].sum())


def class_recall_payload(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """Return recall by class with stable column names."""
    recalls = recall_score(y_true, y_pred, labels=CLASSES, average=None, zero_division=0)
    return {f"recall_class_{class_id}": float(recalls[index]) for index, class_id in enumerate(CLASSES)}


def evaluate_strategy(
    strategy_id: str,
    display_name: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    no_alert_cost: float,
    rule_cost: float,
) -> dict:
    """Evaluate one strategy with classification and official cost metrics."""
    cost = official_cost(y_true, y_pred)
    predicted_distribution = {
        f"predicted_class_{class_id}_count": int((np.asarray(y_pred) == class_id).sum())
        for class_id in CLASSES
    }
    return {
        "strategy_id": strategy_id,
        "display_name": display_name,
        "official_cost": round(cost, 4),
        "normalized_cost": round(cost / no_alert_cost, 6) if no_alert_cost else 0.0,
        "cost_improvement_vs_no_alert": round((no_alert_cost - cost) / no_alert_cost, 6)
        if no_alert_cost
        else 0.0,
        "cost_improvement_vs_rule": round((rule_cost - cost) / rule_cost, 6)
        if rule_cost
        else 0.0,
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6),
        "accuracy": round(float((np.asarray(y_true) == np.asarray(y_pred)).mean()), 6),
        "alert_like_rate": round(float((np.asarray(y_pred) > 0).mean()), 6),
        **{key: round(value, 6) for key, value in class_recall_payload(y_true, y_pred).items()},
        **predicted_distribution,
    }


def choose_rule_feature(X_train: pd.DataFrame, y_train: pd.Series) -> tuple[str, int]:
    """Pick one numeric feature for simple threshold/SPC baselines."""
    positive = (y_train > 0).astype(int)
    scores: dict[str, float] = {}
    signs: dict[str, int] = {}
    for column in X_train.select_dtypes(include=[np.number]).columns[:300]:
        values = X_train[column]
        if values.nunique(dropna=True) <= 1:
            continue
        corr = float(values.corr(positive) or 0.0)
        scores[column] = abs(corr)
        signs[column] = 1 if corr >= 0 else -1
    if not scores:
        first = X_train.columns[0]
        return first, 1
    selected = max(scores, key=scores.get)
    return selected, signs[selected]


def rule_based_predictions(X_train: pd.DataFrame, X_validation: pd.DataFrame, y_train: pd.Series) -> tuple[np.ndarray, str]:
    """Create a simple threshold baseline with five risk bands."""
    feature, sign = choose_rule_feature(X_train, y_train)
    train_score = X_train[feature] * sign
    validation_score = X_validation[feature] * sign
    thresholds = train_score.quantile([0.80, 0.90, 0.95, 0.98]).to_numpy()
    predictions = np.digitize(validation_score.to_numpy(), thresholds, right=False).astype(int)
    return np.clip(predictions, 0, 4), feature


def spc_style_predictions(X_train: pd.DataFrame, X_validation: pd.DataFrame, y_train: pd.Series) -> tuple[np.ndarray, str]:
    """Create a simple SPC-style z-score baseline with five classes."""
    feature, sign = choose_rule_feature(X_train, y_train)
    train_score = X_train[feature] * sign
    validation_score = X_validation[feature] * sign
    mean = float(train_score.mean())
    std = float(train_score.std(ddof=0) or 1.0)
    z_score = (validation_score.to_numpy() - mean) / std
    predictions = np.digitize(z_score, [2.0, 2.5, 3.0, 3.5], right=False).astype(int)
    return np.clip(predictions, 0, 4), feature


def probability_matrix(model_classes: np.ndarray, probabilities: np.ndarray) -> np.ndarray:
    """Return a 5-column probability matrix ordered by official classes."""
    matrix = np.zeros((probabilities.shape[0], len(CLASSES)))
    for index, class_id in enumerate(model_classes.astype(int)):
        matrix[:, class_id] = probabilities[:, index]
    return matrix


def train_and_evaluate(data: ScaniaOfficialData) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Train official class models and evaluate all comparison strategies."""
    X_train, X_validation, y_train, y_validation, feature_columns, raw_feature_columns, categorical_columns = prepare_features(
        data.train,
        data.validation,
    )

    no_alert_pred = np.zeros(len(y_validation), dtype=int)
    rule_pred, rule_feature = rule_based_predictions(X_train, X_validation, y_train)
    spc_pred, spc_feature = spc_style_predictions(X_train, X_validation, y_train)

    logistic = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    logistic.fit(X_train, y_train)
    logistic_pred = logistic.predict(X_validation).astype(int)

    sample_weight = compute_sample_weight("balanced", y_train)
    xgb = XGBClassifier(
        n_estimators=220,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="multi:softprob",
        num_class=5,
        eval_metric="mlogloss",
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    xgb.fit(X_train, y_train, sample_weight=sample_weight)
    xgb_prob = probability_matrix(xgb.classes_, xgb.predict_proba(X_validation))
    xgb_argmax_pred = xgb_prob.argmax(axis=1).astype(int)
    expected_cost = xgb_prob @ OFFICIAL_COST_MATRIX
    xgb_cost_pred = expected_cost.argmin(axis=1).astype(int)

    no_alert_cost = official_cost(y_validation, no_alert_pred)
    rule_cost = official_cost(y_validation, rule_pred)
    strategies = [
        ("no_alert_all_0", "No-alert all class 0", no_alert_pred),
        ("rule_based_threshold", f"Rule-based threshold ({rule_feature})", rule_pred),
        ("spc_style_baseline", f"SPC-style baseline ({spc_feature})", spc_pred),
        ("logistic_multiclass", "Logistic Regression multiclass", logistic_pred),
        ("xgboost_multiclass_argmax", "XGBoost multiclass argmax", xgb_argmax_pred),
        ("xgboost_cost_optimized", "XGBoost official-cost optimized", xgb_cost_pred),
    ]
    rows = [
        evaluate_strategy(strategy_id, display_name, y_validation, y_pred, no_alert_cost, rule_cost)
        for strategy_id, display_name, y_pred in strategies
    ]
    metrics_df = pd.DataFrame(rows).sort_values("official_cost", ascending=True)

    predictions_df = data.validation[["vehicle_id", "time_step", "class_label"]].copy()
    predictions_df = predictions_df.rename(columns={"class_label": "actual_class"})
    for strategy_id, _, y_pred in strategies:
        predictions_df[f"{strategy_id}_predicted_class"] = y_pred
    for class_id in CLASSES:
        predictions_df[f"xgboost_probability_class_{class_id}"] = xgb_prob[:, class_id]
    predictions_df["xgboost_expected_cost_min"] = expected_cost.min(axis=1)

    metadata = {
        "source_note": data.source_note,
        "train_rows": int(len(data.train)),
        "validation_rows": int(len(data.validation)),
        "feature_count": int(len(feature_columns)),
        "train_class_distribution": {
            str(class_id): int((data.train["class_label"] == class_id).sum()) for class_id in CLASSES
        },
        "validation_class_distribution": {
            str(class_id): int((data.validation["class_label"] == class_id).sum()) for class_id in CLASSES
        },
        "official_cost_matrix": OFFICIAL_COST_MATRIX.astype(int).tolist(),
        "class_windows": CLASS_WINDOWS,
    }
    artifact = {
        "model": xgb,
        "model_type": "xgboost_cost_optimized",
        "feature_columns": feature_columns,
        "raw_feature_columns": raw_feature_columns,
        "categorical_columns": categorical_columns,
        "fill_values": X_train.median(numeric_only=True).fillna(0).to_dict(),
        "official_cost_matrix": OFFICIAL_COST_MATRIX.astype(int).tolist(),
        "classes": CLASSES,
        "class_windows": CLASS_WINDOWS,
        "metadata": metadata,
    }
    return metrics_df, predictions_df, metadata, artifact


def write_charts(metrics_df: pd.DataFrame, predictions_df: pd.DataFrame) -> None:
    """Write cost comparison and confusion-matrix charts."""
    chart_df = metrics_df.sort_values("official_cost", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.barh(chart_df["display_name"], chart_df["official_cost"], color="#0f766e")
    ax.set_xlabel("Official SCANIA cost metric")
    ax.set_title("SCANIA Official Cost Comparison")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(COST_CHART, dpi=240, bbox_inches="tight")
    plt.close(fig)

    best_strategy = metrics_df.iloc[0]["strategy_id"]
    y_true = predictions_df["actual_class"].to_numpy(dtype=int)
    y_pred = predictions_df[f"{best_strategy}_predicted_class"].to_numpy(dtype=int)
    matrix = confusion_matrix(y_true, y_pred, labels=CLASSES)
    fig, ax = plt.subplots(figsize=(6, 5))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(CLASSES)
    ax.set_yticks(CLASSES)
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("Actual class")
    ax.set_title(f"Confusion Matrix: {best_strategy}")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            ax.text(col, row, str(matrix[row, col]), ha="center", va="center", color="#111827")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(CONFUSION_CHART, dpi=240, bbox_inches="tight")
    plt.close(fig)


def write_report(metrics_df: pd.DataFrame, metadata: dict) -> None:
    """Write a thesis-safe official benchmark report."""
    best = metrics_df.iloc[0]
    rule = metrics_df[metrics_df["strategy_id"] == "rule_based_threshold"].iloc[0]
    no_alert = metrics_df[metrics_df["strategy_id"] == "no_alert_all_0"].iloc[0]
    report = [
        "# SCANIA Official Cost Metric Validation",
        "",
        "## Scope",
        "",
        (
            "This report is a public benchmark validation using SCANIA Component X official "
            "class labels and official misclassification cost matrix. It is not site-specific "
            "factory deployment proof and not real KRW maintenance-cost reduction proof."
        ),
        "",
        f"- Source: {metadata['source_note']}",
        f"- Train rows sampled: `{metadata['train_rows']}`",
        f"- Validation vehicles: `{metadata['validation_rows']}`",
        f"- Feature columns after encoding: `{metadata['feature_count']}`",
        f"- Train class distribution: `{metadata['train_class_distribution']}`",
        f"- Validation class distribution: `{metadata['validation_class_distribution']}`",
        "",
        "## Official Class Definition",
        "",
        "| Class | Meaning |",
        "|---:|---|",
    ]
    for class_id, meaning in CLASS_WINDOWS.items():
        report.append(f"| {class_id} | {meaning} |")
    report.extend(
        [
            "",
            "## Best Official Cost Strategy",
            "",
            f"- Strategy: `{best['display_name']}`",
            f"- Official cost: `{best['official_cost']:.0f}`",
            f"- Normalized cost vs no-alert: `{best['normalized_cost']:.4f}`",
            f"- Cost improvement vs no-alert: `{best['cost_improvement_vs_no_alert']:.2%}`",
            f"- Cost improvement vs rule baseline: `{best['cost_improvement_vs_rule']:.2%}`",
            f"- Alert-like prediction rate: `{best['alert_like_rate']:.2%}`",
            f"- Macro F1: `{best['macro_f1']:.4f}`",
            f"- Balanced accuracy: `{best['balanced_accuracy']:.4f}`",
            "",
            "## Baseline Reference",
            "",
            f"- No-alert cost: `{no_alert['official_cost']:.0f}`",
            f"- Rule baseline cost: `{rule['official_cost']:.0f}`",
            "",
            "## Claim Guardrail",
            "",
            (
                "Use the phrase `SCANIA official cost metric improvement` rather than "
                "`actual maintenance cost reduction`. Actual field cost reduction or lead-time "
                "shortening requires company-specific before/after operations, repair, downtime, "
                "and cost logs."
            ),
            (
                "Also report the alert-like prediction rate. The official matrix heavily penalizes "
                "missed late failures, so a low official cost can still imply many inspections."
            ),
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(report), encoding="utf-8")


def write_outputs(metrics_df: pd.DataFrame, predictions_df: pd.DataFrame, metadata: dict, artifact: dict) -> None:
    """Persist all official SCANIA benchmark outputs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(METRICS_CSV, index=False, encoding="utf-8-sig")
    predictions_df.to_csv(PREDICTIONS_CSV, index=False, encoding="utf-8-sig")
    METRICS_JSON.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "metrics": metrics_df.to_dict(orient="records"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    joblib.dump(artifact, MODEL_ARTIFACT)
    write_charts(metrics_df, predictions_df)
    write_report(metrics_df, metadata)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate SCANIA Component X official class 0~4 cost metric."
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directory containing SCANIA Component X train and validation CSV files.",
    )
    parser.add_argument(
        "--max-rows-per-class",
        type=int,
        default=10000,
        help="Maximum training rows to sample per official class.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=200000,
        help="Chunk size used while reading the large train operational CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_scania_official_data(
        Path(args.data_dir),
        max_rows_per_class=args.max_rows_per_class,
        chunk_size=args.chunk_size,
    )
    metrics_df, predictions_df, metadata, artifact = train_and_evaluate(data)
    write_outputs(metrics_df, predictions_df, metadata, artifact)

    best = metrics_df.iloc[0]
    print("SCANIA official cost validation finished successfully.")
    print(f"best_strategy: {best['strategy_id']}")
    print(f"official_cost: {best['official_cost']:.0f}")
    print(f"cost_improvement_vs_rule: {best['cost_improvement_vs_rule']:.2%}")
    print(f"metrics_csv: {METRICS_CSV}")
    print(f"report_md: {REPORT_MD}")
    print(f"model_artifact: {MODEL_ARTIFACT}")


if __name__ == "__main__":
    main()
