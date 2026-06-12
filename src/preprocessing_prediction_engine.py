from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score

from data import load_data, preprocess_data, preprocess_features
from final_policy import FINAL_POLICY_ID, FINAL_PROBABILITY_BASIS, FINAL_RAW_THRESHOLD, final_policy_dict
from thesis_methodology_validation import split_60_20_20
from train_baseline import RANDOM_STATE, build_models


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

QUALITY_CSV = OUTPUT_DIR / "company_input_quality_report.csv"
QUALITY_JSON = OUTPUT_DIR / "company_input_quality_report.json"
PREPROCESSING_MD = OUTPUT_DIR / "company_preprocessing_report.md"
CALIBRATION_JSON = OUTPUT_DIR / "probability_calibration_metrics.json"
CALIBRATION_PNG = OUTPUT_DIR / "probability_calibration_curve.png"
CONFIDENCE_MD = OUTPUT_DIR / "prediction_confidence_report.md"
POLICY_JSON = OUTPUT_DIR / "operating_policy_thresholds.json"
PREDICTIONS_CSV = OUTPUT_DIR / "company_prediction_results.csv"
PRIORITY_CSV = OUTPUT_DIR / "company_risk_priority_queue.csv"
POLICY_MD = OUTPUT_DIR / "operating_policy_simulation.md"

CANONICAL_SENSOR_COLUMNS = [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]

NUMERIC_SENSOR_COLUMNS = [column for column in CANONICAL_SENSOR_COLUMNS if column != "Type"]

UNIT_OPTIONS = [
    "Auto",
    "No conversion",
    "Celsius -> Kelvin",
    "Kelvin -> Celsius",
    "Seconds -> Minutes",
    "Minutes -> Seconds",
]

COLUMN_ALIASES = {
    "Type": [
        "type",
        "product_type",
        "product grade",
        "grade",
        "material",
        "제품",
        "제품등급",
        "제품 등급",
        "제품타입",
        "제품 타입",
        "타입",
        "등급",
        "설비타입",
        "설비 타입",
    ],
    "Air temperature [K]": [
        "air temperature",
        "air_temperature",
        "airtemp",
        "air_temp",
        "ambient_temperature",
        "ambient_temp",
        "room_temperature",
        "공기온도",
        "공기 온도",
        "대기온도",
        "대기 온도",
        "주변온도",
        "주변 온도",
        "온도",
    ],
    "Process temperature [K]": [
        "process temperature",
        "process_temperature",
        "process_temp",
        "processtemp",
        "machine_temperature",
        "설비온도",
        "설비 온도",
        "공정온도",
        "공정 온도",
        "기계온도",
        "기계 온도",
    ],
    "Rotational speed [rpm]": [
        "rotational speed",
        "rotational_speed",
        "rotation_speed",
        "rpm",
        "speed",
        "spindle_speed",
        "회전속도",
        "회전 속도",
        "스핀들속도",
        "스핀들 속도",
    ],
    "Torque [Nm]": [
        "torque",
        "torque_nm",
        "motor_torque",
        "motor torque",
        "load",
        "motor_load",
        "motor load",
        "토크",
        "모터토크",
        "모터 토크",
        "부하",
        "모터부하",
        "모터 부하",
    ],
    "Tool wear [min]": [
        "tool wear",
        "tool_wear",
        "wear",
        "wear_min",
        "runtime",
        "usage_time",
        "operation_time",
        "사용시간",
        "사용 시간",
        "운전시간",
        "운전 시간",
        "공구마모",
        "공구 마모",
        "공구마모시간",
        "공구 마모 시간",
        "마모",
    ],
}

OPERATING_POLICY_LABELS = {
    "precision_first": "Precision-first",
    "balanced": "Balanced",
    "recall_first": "Recall-first",
}


@dataclass
class CalibrationChoice:
    method: str
    brier_score: float
    calibrator: object


def normalize_name(value: str) -> str:
    """Normalize a column name for alias matching."""
    value = str(value).strip().lower()
    value = re.sub(r"[\[\]\(\)\{\}/\\._\-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def compact_name(value: str) -> str:
    """Return a compact name for fuzzy alias matching."""
    return re.sub(r"[^0-9a-z가-힣]+", "", normalize_name(value))


def column_match_score(source_column: str, aliases: list[str]) -> float:
    """Return a simple deterministic alias score."""
    source_normal = normalize_name(source_column)
    source_compact = compact_name(source_column)
    best = 0.0
    for alias in aliases:
        alias_normal = normalize_name(alias)
        alias_compact = compact_name(alias)
        if source_normal == alias_normal or source_compact == alias_compact:
            best = max(best, 1.0)
        elif alias_compact and alias_compact in source_compact:
            best = max(best, 0.88)
        elif source_compact and source_compact in alias_compact:
            best = max(best, 0.72)
    return best


def infer_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
    """Infer likely source columns for the canonical AI4I sensor schema."""
    rows = []
    used_columns: set[str] = set()
    for canonical in CANONICAL_SENSOR_COLUMNS:
        best_column = ""
        best_score = 0.0
        for source_column in df.columns:
            if source_column in used_columns:
                continue
            score = column_match_score(source_column, [canonical, *COLUMN_ALIASES[canonical]])
            if score > best_score:
                best_column = str(source_column)
                best_score = score
        if best_score >= 0.65:
            used_columns.add(best_column)
        else:
            best_column = ""
            best_score = 0.0
        rows.append(
            {
                "canonical_column": canonical,
                "suggested_source_column": best_column,
                "confidence": round(float(best_score), 3),
                "required": True,
            }
        )
    return pd.DataFrame(rows)


def sample_company_alias_dataframe() -> pd.DataFrame:
    """Return a sample company-style CSV with different names and Celsius units."""
    return pd.DataFrame(
        [
            {
                "product_grade": "L",
                "air_temp_c": 25.0,
                "process_temp_c": 35.4,
                "rpm": 1551,
                "motor_torque_nm": 42.8,
                "wear_minutes": 0,
            },
            {
                "product_grade": "M",
                "air_temp_c": 26.1,
                "process_temp_c": 36.6,
                "rpm": 1408,
                "motor_torque_nm": 46.3,
                "wear_minutes": 3,
            },
            {
                "product_grade": "H",
                "air_temp_c": 30.2,
                "process_temp_c": 39.8,
                "rpm": 1320,
                "motor_torque_nm": 58.2,
                "wear_minutes": 120,
            },
        ]
    )


def make_reference_profile(raw_df: pd.DataFrame) -> dict:
    """Build reference medians and loose operating ranges from AI4I."""
    profile = {}
    for column in NUMERIC_SENSOR_COLUMNS:
        values = pd.to_numeric(raw_df[column], errors="coerce")
        q1 = float(values.quantile(0.01))
        q99 = float(values.quantile(0.99))
        spread = max(q99 - q1, 1.0)
        profile[column] = {
            "median": float(values.median()),
            "min": float(values.min()),
            "max": float(values.max()),
            "loose_min": q1 - spread * 0.25,
            "loose_max": q99 + spread * 0.25,
        }
    return profile


def infer_unit_conversion(canonical_column: str, values: pd.Series, requested: str) -> tuple[pd.Series, str]:
    """Apply or infer a unit conversion for one numeric column."""
    numeric_values = pd.to_numeric(values, errors="coerce")
    conversion = requested or "Auto"
    applied = conversion
    if conversion == "Auto":
        median = float(numeric_values.dropna().median()) if numeric_values.notna().any() else 0.0
        if canonical_column in {"Air temperature [K]", "Process temperature [K]"} and -50 <= median <= 120:
            applied = "Celsius -> Kelvin"
        else:
            applied = "No conversion"

    if applied == "Celsius -> Kelvin":
        return numeric_values + 273.15, applied
    if applied == "Kelvin -> Celsius":
        return numeric_values - 273.15, applied
    if applied == "Seconds -> Minutes":
        return numeric_values / 60.0, applied
    if applied == "Minutes -> Seconds":
        return numeric_values * 60.0, applied
    return numeric_values, "No conversion"


def build_quality_row(
    canonical_column: str,
    source_column: str,
    issue: str,
    severity: str,
    affected_rows: int,
    detail: str,
) -> dict:
    """Create one human-readable quality report row."""
    return {
        "canonical_column": canonical_column,
        "source_column": source_column,
        "issue": issue,
        "severity": severity,
        "affected_rows": int(affected_rows),
        "detail": detail,
    }


def prepare_company_sensor_csv(
    df: pd.DataFrame,
    mapping: dict[str, str] | None = None,
    unit_conversions: dict[str, str] | None = None,
    reference_profile: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Map a company CSV into the canonical AI4I sensor schema and report quality."""
    mapping = mapping or dict(
        zip(
            infer_column_mapping(df)["canonical_column"],
            infer_column_mapping(df)["suggested_source_column"],
        )
    )
    unit_conversions = unit_conversions or {}
    reference_profile = reference_profile or {}
    canonical_df = pd.DataFrame(index=df.index)
    quality_rows = []
    applied_conversions = {}

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows:
        quality_rows.append(
            build_quality_row(
                "all",
                "all",
                "duplicate_rows",
                "warning",
                duplicate_rows,
                "Duplicate rows are kept for prediction but flagged for review.",
            )
        )

    for canonical in CANONICAL_SENSOR_COLUMNS:
        source = str(mapping.get(canonical, "") or "")
        if canonical == "Type":
            if not source or source not in df.columns:
                canonical_df[canonical] = "M"
                quality_rows.append(
                    build_quality_row(
                        canonical,
                        source,
                        "missing_column",
                        "warning",
                        len(df),
                        "Type was not mapped. Default Type=M was used for local prediction.",
                    )
                )
                continue
            values = df[source].fillna("M").astype(str).str.strip().str.upper()
            invalid_mask = ~values.isin(["L", "M", "H"])
            if invalid_mask.any():
                values.loc[invalid_mask] = "M"
                quality_rows.append(
                    build_quality_row(
                        canonical,
                        source,
                        "invalid_type",
                        "warning",
                        int(invalid_mask.sum()),
                        "Unsupported Type values were replaced with M.",
                    )
                )
            canonical_df[canonical] = values
            continue

        ref = reference_profile.get(canonical, {})
        fill_value = float(ref.get("median", 0.0))
        if not source or source not in df.columns:
            canonical_df[canonical] = fill_value
            applied_conversions[canonical] = "No conversion"
            quality_rows.append(
                build_quality_row(
                    canonical,
                    source,
                    "missing_column",
                    "error",
                    len(df),
                    f"Column was not mapped. Filled with reference median {fill_value:.4f}.",
                )
            )
            continue

        raw_values = df[source]
        converted, applied = infer_unit_conversion(
            canonical,
            raw_values,
            unit_conversions.get(canonical, "Auto"),
        )
        applied_conversions[canonical] = applied
        invalid_numeric_mask = converted.isna() & raw_values.notna()
        missing_mask = raw_values.isna() | (raw_values.astype(str).str.strip() == "")
        if invalid_numeric_mask.any():
            quality_rows.append(
                build_quality_row(
                    canonical,
                    source,
                    "numeric_conversion_failed",
                    "error",
                    int(invalid_numeric_mask.sum()),
                    "Values that could not be converted to numbers were filled with the column/reference median.",
                )
            )
        if missing_mask.any():
            quality_rows.append(
                build_quality_row(
                    canonical,
                    source,
                    "missing_values",
                    "warning",
                    int(missing_mask.sum()),
                    "Missing values were filled with the column/reference median.",
                )
            )

        fill = float(converted.median()) if converted.notna().any() else fill_value
        cleaned_values = converted.fillna(fill)
        loose_min = ref.get("loose_min")
        loose_max = ref.get("loose_max")
        if loose_min is not None and loose_max is not None:
            out_of_range = (cleaned_values < float(loose_min)) | (cleaned_values > float(loose_max))
            if out_of_range.any():
                quality_rows.append(
                    build_quality_row(
                        canonical,
                        source,
                        "outside_training_range",
                        "warning",
                        int(out_of_range.sum()),
                        "Values are outside the loose AI4I reference range; prediction confidence is reduced.",
                    )
                )
        canonical_df[canonical] = cleaned_values

    quality_df = pd.DataFrame(quality_rows)
    if quality_df.empty:
        quality_df = pd.DataFrame(
            [
                build_quality_row(
                    "all",
                    "",
                    "no_blocking_issue",
                    "info",
                    0,
                    "No blocking data-quality issue was found.",
                )
            ]
        )

    error_rows = int(quality_df.loc[quality_df["severity"] == "error", "affected_rows"].sum())
    warning_rows = int(quality_df.loc[quality_df["severity"] == "warning", "affected_rows"].sum())
    total_cells = max(len(df) * len(CANONICAL_SENSOR_COLUMNS), 1)
    quality_score = max(0.0, 100.0 - (error_rows / total_cells) * 80.0 - (warning_rows / total_cells) * 35.0)
    drift_warning_count = int(
        quality_df.loc[quality_df["issue"] == "outside_training_range", "affected_rows"].sum()
    )
    report = {
        "row_count": int(len(df)),
        "source_column_count": int(len(df.columns)),
        "mapped_columns": mapping,
        "applied_unit_conversions": applied_conversions,
        "quality_score": round(float(quality_score), 2),
        "quality_status": "Low" if quality_score < 70 else "Medium" if quality_score < 90 else "High",
        "duplicate_rows": duplicate_rows,
        "error_rows": error_rows,
        "warning_rows": warning_rows,
        "drift_warning_count": drift_warning_count,
        "prediction_scope": "unlabeled company CSV prediction and quality diagnosis",
    }
    return canonical_df, quality_df, report


def threshold_metrics(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict:
    """Calculate operating metrics for one threshold."""
    y_pred = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 2),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
        "alert_count": int(fp + tp),
        "false_alarm_count": int(fp),
        "missed_failure_count": int(fn),
        "true_positive_count": int(tp),
        "true_negative_count": int(tn),
    }


def choose_operating_policies(y_true: pd.Series, probabilities: np.ndarray) -> dict:
    """Choose three stable operating thresholds for product use."""
    rows = []
    for threshold in np.arange(0.05, 0.951, 0.01):
        rows.append(threshold_metrics(y_true, probabilities, float(threshold)))
    threshold_df = pd.DataFrame(rows)
    balanced = threshold_df.sort_values(["f1_score", "recall"], ascending=[False, False]).iloc[0]
    precision_candidates = threshold_df[threshold_df["precision"] >= 0.8]
    precision_first = (
        precision_candidates.sort_values(["recall", "f1_score"], ascending=[False, False]).iloc[0]
        if not precision_candidates.empty
        else threshold_df.sort_values(["precision", "f1_score"], ascending=[False, False]).iloc[0]
    )
    recall_candidates = threshold_df[threshold_df["recall"] >= 0.85]
    recall_first = (
        recall_candidates.sort_values(["precision", "f1_score"], ascending=[False, False]).iloc[0]
        if not recall_candidates.empty
        else threshold_df.sort_values(["recall", "f1_score"], ascending=[False, False]).iloc[0]
    )
    return {
        "precision_first": precision_first.to_dict(),
        "balanced": balanced.to_dict(),
        "recall_first": recall_first.to_dict(),
        "threshold_grid": threshold_df.round(4).to_dict(orient="records"),
    }


def fit_sigmoid_calibrator(raw_probabilities: np.ndarray, y_true: pd.Series) -> LogisticRegression:
    """Fit a one-dimensional Platt-style sigmoid calibrator."""
    calibrator = LogisticRegression(solver="lbfgs")
    calibrator.fit(raw_probabilities.reshape(-1, 1), y_true)
    return calibrator


def apply_calibrator(calibrator: object, probabilities: np.ndarray) -> np.ndarray:
    """Apply either sigmoid or isotonic calibration."""
    if isinstance(calibrator, LogisticRegression):
        return calibrator.predict_proba(probabilities.reshape(-1, 1))[:, 1]
    return calibrator.predict(probabilities)


def save_calibration_plot(y_true: pd.Series, traces: dict[str, np.ndarray]) -> None:
    """Save a calibration curve comparing raw, sigmoid, and isotonic probabilities."""
    plt.figure(figsize=(7.8, 6.0))
    plt.plot([0, 1], [0, 1], linestyle="--", color="#666666", label="Perfect calibration")
    for label, probabilities in traces.items():
        fraction, mean_predicted = calibration_curve(y_true, probabilities, n_bins=8, strategy="quantile")
        plt.plot(mean_predicted, fraction, marker="o", label=label)
    plt.xlabel("Mean predicted probability")
    plt.ylabel("Observed failure fraction")
    plt.title("Probability Calibration Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(CALIBRATION_PNG, dpi=160)
    plt.close()


@lru_cache(maxsize=1)
def train_smart_prediction_bundle() -> dict:
    """Train XGBoost and calibration helpers with the final 60:20:20 split."""
    raw_df = load_data(DATA_PATH)
    X, y = preprocess_data(raw_df)
    split = split_60_20_20(X, y, RANDOM_STATE)
    model = build_models(split.y_train)["xgboost"]
    model.fit(split.X_train, split.y_train)

    raw_valid = model.predict_proba(split.X_valid)[:, 1]
    raw_test = model.predict_proba(split.X_test)[:, 1]
    sigmoid = fit_sigmoid_calibrator(raw_valid, split.y_valid)
    isotonic = IsotonicRegression(out_of_bounds="clip")
    isotonic.fit(raw_valid, split.y_valid)
    sigmoid_valid = apply_calibrator(sigmoid, raw_valid)
    isotonic_valid = apply_calibrator(isotonic, raw_valid)
    sigmoid_test = apply_calibrator(sigmoid, raw_test)
    isotonic_test = apply_calibrator(isotonic, raw_test)

    choices = [
        CalibrationChoice("raw", brier_score_loss(split.y_valid, raw_valid), None),
        CalibrationChoice("sigmoid", brier_score_loss(split.y_valid, sigmoid_valid), sigmoid),
        CalibrationChoice("isotonic", brier_score_loss(split.y_valid, isotonic_valid), isotonic),
    ]
    best = sorted(choices, key=lambda choice: choice.brier_score)[0]
    valid_calibrated = raw_valid if best.method == "raw" else apply_calibrator(best.calibrator, raw_valid)
    policies = choose_operating_policies(split.y_valid, valid_calibrated)
    final_policy = final_policy_dict()

    save_calibration_plot(
        split.y_test,
        {
            "raw": raw_test,
            "sigmoid": sigmoid_test,
            "isotonic": isotonic_test,
        },
    )
    calibration_payload = {
        "scope": "AI4I validation calibration for probability display; app decision uses raw threshold 0.86",
        "selected_method": best.method,
        "selection_basis": "validation Brier score",
        "validation_brier_scores": {choice.method: round(float(choice.brier_score), 6) for choice in choices},
        "brier_scores": {choice.method: round(float(choice.brier_score), 6) for choice in choices},
        "test_brier_scores": {
            "raw": round(float(brier_score_loss(split.y_test, raw_test)), 6),
            "sigmoid": round(float(brier_score_loss(split.y_test, sigmoid_test)), 6),
            "isotonic": round(float(brier_score_loss(split.y_test, isotonic_test)), 6),
        },
        "test_rows": int(len(split.y_test)),
        "test_failures": int(split.y_test.sum()),
    }
    CALIBRATION_JSON.write_text(json.dumps(calibration_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    POLICY_JSON.write_text(
        json.dumps(
            {
                "scope": "app decision uses raw probability threshold 0.86; calibrated thresholds are reference policies only",
                "final_decision_policy": final_policy,
                "policies": {
                    key: {
                        field: round(float(value[field]), 4)
                        if field in {"threshold", "precision", "recall", "f1_score"}
                        else int(value[field])
                        for field in [
                            "threshold",
                            "precision",
                            "recall",
                            "f1_score",
                            "alert_count",
                            "false_alarm_count",
                            "missed_failure_count",
                        ]
                    }
                    for key, value in policies.items()
                    if key != "threshold_grid"
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return {
        "model": model,
        "feature_columns": list(split.X_train.columns),
        "calibration_method": best.method,
        "calibrator": best.calibrator,
        "final_policy": final_policy,
        "policies": policies,
        "reference_profile": make_reference_profile(raw_df),
        "calibration_metrics": calibration_payload,
    }


def calculate_priority_scores(
    probabilities: np.ndarray,
    threshold: float,
    quality_score: float,
    missed_failure_weight: float = 15.0,
    false_alarm_weight: float = 1.0,
) -> np.ndarray:
    """Convert probabilities and data quality into a 0-100 priority score."""
    probability_component = probabilities * 72.0
    threshold_component = (probabilities >= threshold).astype(float) * 14.0
    quality_component = max(0.0, 100.0 - quality_score) * 0.14
    cost_component = np.clip(missed_failure_weight / max(false_alarm_weight, 0.1), 0, 30) / 30.0 * 10.0
    return np.clip(probability_component + threshold_component + quality_component + cost_component, 0, 100)


def recommendation_for_row(probability: float, threshold: float, priority_score: float, quality_status: str) -> str:
    """Return a concise operator-facing recommendation."""
    if probability >= threshold and priority_score >= 80:
        return "최우선 점검: 운전 지속 전 토크/부하, 온도, 공구 마모 상태를 확인하세요."
    if probability >= threshold:
        return "주의 경보: 센서 맥락을 검토하고 작업자 승인용 작업지시 초안을 생성하세요."
    if quality_status == "Low":
        return "데이터 품질 낮음: 이 확률을 사용하기 전 원본 데이터 형식과 결측값을 먼저 보정하세요."
    return "모니터링 유지: 현재 기준 미만이지만 추세 이력은 계속 확인하세요."


def write_preprocessing_report(quality_df: pd.DataFrame, report: dict) -> None:
    """Write a markdown preprocessing report."""
    rows = [
        "# Company CSV Preprocessing Report",
        "",
        "## Scope",
        "",
        "This report describes company CSV mapping and quality checks for prediction. It does not prove real company-data model performance unless labels are supplied and evaluated separately.",
        "",
        f"- Rows: {report['row_count']}",
        f"- Source columns: {report['source_column_count']}",
        f"- Quality score: {report['quality_score']}",
        f"- Quality status: {report['quality_status']}",
        "",
        "## Column Mapping",
        "",
        "| Canonical column | Source column | Unit conversion |",
        "|---|---|---|",
    ]
    for canonical, source in report["mapped_columns"].items():
        rows.append(
            f"| {canonical} | {source or '(default/fill)'} | {report['applied_unit_conversions'].get(canonical, '')} |"
        )
    rows.extend(
        [
            "",
            "## Quality Issues",
            "",
            "| Column | Issue | Severity | Affected rows | Detail |",
            "|---|---|---|---:|---|",
        ]
    )
    for _, row in quality_df.iterrows():
        rows.append(
            f"| {row['canonical_column']} | {row['issue']} | {row['severity']} | {int(row['affected_rows'])} | {row['detail']} |"
        )
    PREPROCESSING_MD.write_text("\n".join(rows), encoding="utf-8")


def write_confidence_report(report: dict, calibration_metrics: dict) -> None:
    """Write a markdown report explaining prediction confidence."""
    rows = [
        "# Prediction Confidence Report",
        "",
        "## Scope",
        "",
        "Confidence combines input data quality, AI4I reference-range checks, and validation-set probability calibration. It is not a field-certified reliability score.",
        "",
        f"- Selected calibration method: {calibration_metrics['selected_method']}",
        f"- Quality score: {report['quality_score']}",
        f"- Quality status: {report['quality_status']}",
        f"- Drift warning count: {report['drift_warning_count']}",
        "",
        "## Validation Brier Scores",
        "",
        "| Method | Brier score |",
        "|---|---:|",
    ]
    for method, score in calibration_metrics["validation_brier_scores"].items():
        rows.append(f"| {method} | {score:.6f} |")
    rows.extend(
        [
            "",
            "## Guardrail",
            "",
            "Low confidence means the user should inspect mapping, units, missing values, and training-distribution drift before using the risk result.",
        ]
    )
    CONFIDENCE_MD.write_text("\n".join(rows), encoding="utf-8")


def write_policy_simulation(policies: dict, selected_policy: str) -> None:
    """Write operating policy threshold notes."""
    rows = [
        "# Operating Policy Simulation",
        "",
        "## Scope",
        "",
        "These thresholds are derived from the AI4I validation/test split and are not factory-approved operating policies.",
        "",
        f"- Selected policy for the latest company CSV prediction: `{selected_policy}`",
        "",
        "| Policy | Threshold | Precision | Recall | F1 | Alerts | False alarms | Missed failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy_id in ["precision_first", "balanced", "recall_first"]:
        row = policies[policy_id]
        rows.append(
            f"| {OPERATING_POLICY_LABELS[policy_id]} | {row['threshold']:.2f} | "
            f"{row['precision']:.4f} | {row['recall']:.4f} | {row['f1_score']:.4f} | "
            f"{int(row['alert_count'])} | {int(row['false_alarm_count'])} | {int(row['missed_failure_count'])} |"
        )
    rows.extend(
        [
            "",
            "## Guardrail",
            "",
            "Use these policies to discuss trade-offs. Do not claim real factory threshold approval or actual cost reduction.",
        ]
    )
    POLICY_MD.write_text("\n".join(rows), encoding="utf-8")


def predict_company_sensor_csv(
    df: pd.DataFrame,
    mapping: dict[str, str] | None = None,
    unit_conversions: dict[str, str] | None = None,
    policy_id: str = "balanced",
    write_outputs: bool = True,
) -> dict:
    """Run smart company CSV mapping, quality diagnosis, calibrated prediction, and priority ranking."""
    bundle = train_smart_prediction_bundle()
    canonical_df, quality_df, quality_report = prepare_company_sensor_csv(
        df,
        mapping=mapping,
        unit_conversions=unit_conversions,
        reference_profile=bundle["reference_profile"],
    )
    features = preprocess_features(canonical_df, expected_columns=bundle["feature_columns"])
    raw_probability = bundle["model"].predict_proba(features)[:, 1]
    if bundle["calibration_method"] == "raw":
        calibrated_probability = raw_probability
    else:
        calibrated_probability = apply_calibrator(bundle["calibrator"], raw_probability)

    policy_id = policy_id if policy_id in {"precision_first", "balanced", "recall_first"} else "balanced"
    selected_policy = bundle["final_policy"]
    threshold = float(selected_policy["threshold"])
    priority_scores = calculate_priority_scores(
        raw_probability,
        threshold,
        float(quality_report["quality_score"]),
    )
    result_df = canonical_df.copy()
    result_df.insert(0, "input_row", range(len(result_df)))
    result_df["engine_profile"] = "full"
    result_df["score_method"] = "정밀 예측 엔진"
    result_df["interpretation_note"] = (
        "정밀 분석 모드 결과입니다. XGBoost 기반 예측 확률, calibration, 운영 정책 threshold를 적용했습니다."
    )
    result_df["raw_probability"] = np.round(raw_probability, 6)
    result_df["calibrated_probability"] = np.round(calibrated_probability, 6)
    result_df["operating_policy"] = FINAL_POLICY_ID
    result_df["reference_policy"] = policy_id
    result_df["probability_basis"] = FINAL_PROBABILITY_BASIS
    result_df["selected_threshold"] = round(threshold, 4)
    result_df["risk_status"] = np.where(raw_probability >= threshold, "High Risk", "Normal")
    result_df["risk_priority_score"] = np.round(priority_scores, 2)
    result_df["data_quality_status"] = quality_report["quality_status"]
    result_df["recommendation"] = [
        recommendation_for_row(float(prob), threshold, float(score), quality_report["quality_status"])
        for prob, score in zip(raw_probability, priority_scores)
    ]

    priority_df = result_df.sort_values(
        ["risk_priority_score", "raw_probability"],
        ascending=[False, False],
    ).reset_index(drop=True)
    priority_df.insert(0, "priority_rank", range(1, len(priority_df) + 1))

    if write_outputs:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        quality_df.to_csv(QUALITY_CSV, index=False, encoding="utf-8-sig")
        QUALITY_JSON.write_text(json.dumps(quality_report, indent=2, ensure_ascii=False), encoding="utf-8")
        write_preprocessing_report(quality_df, quality_report)
        result_df.to_csv(PREDICTIONS_CSV, index=False, encoding="utf-8-sig")
        priority_df.to_csv(PRIORITY_CSV, index=False, encoding="utf-8-sig")
        write_confidence_report(quality_report, bundle["calibration_metrics"])
        write_policy_simulation(bundle["policies"], policy_id)

    return {
        "canonical_df": canonical_df,
        "quality_df": quality_df,
        "quality_report": quality_report,
        "result_df": result_df,
        "priority_df": priority_df,
        "policy_id": FINAL_POLICY_ID,
        "reference_policy_id": policy_id,
        "policy": selected_policy,
        "policies": bundle["policies"],
        "calibration_metrics": bundle["calibration_metrics"],
        "engine_profile": "full",
        "score_method": "정밀 예측 엔진",
        "interpretation_note": "정밀 분석 모드의 XGBoost 기반 분석 결과입니다.",
        "calibration_curve_path": str(CALIBRATION_PNG),
        "output_path": PREDICTIONS_CSV,
        "output_paths": {
            "quality_csv": str(QUALITY_CSV),
            "quality_json": str(QUALITY_JSON),
            "preprocessing_report": str(PREPROCESSING_MD),
            "calibration_metrics": str(CALIBRATION_JSON),
            "calibration_curve": str(CALIBRATION_PNG),
            "confidence_report": str(CONFIDENCE_MD),
            "policy_json": str(POLICY_JSON),
            "predictions_csv": str(PREDICTIONS_CSV),
            "priority_csv": str(PRIORITY_CSV),
            "policy_report": str(POLICY_MD),
        },
    }


def main() -> None:
    """Generate smart preprocessing/prediction artifacts from a sample company CSV."""
    sample = sample_company_alias_dataframe()
    mapping_df = infer_column_mapping(sample)
    mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
    unit_conversions = {
        "Air temperature [K]": "Auto",
        "Process temperature [K]": "Auto",
        "Rotational speed [rpm]": "No conversion",
        "Torque [Nm]": "No conversion",
        "Tool wear [min]": "No conversion",
    }
    result = predict_company_sensor_csv(
        sample,
        mapping=mapping,
        unit_conversions=unit_conversions,
        policy_id="balanced",
        write_outputs=True,
    )
    print("Smart preprocessing prediction engine finished successfully.")
    print(f"rows: {len(result['result_df'])}")
    print(f"quality_score: {result['quality_report']['quality_score']}")
    print(f"selected_policy: {result['policy_id']}")
    for label, path in result["output_paths"].items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
