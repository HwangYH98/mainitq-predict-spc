from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from preprocessing_prediction_engine import (
    CALIBRATION_JSON,
    CALIBRATION_PNG,
    CONFIDENCE_MD,
    POLICY_JSON,
    POLICY_MD,
    PREDICTIONS_CSV,
    PREPROCESSING_MD,
    PRIORITY_CSV,
    QUALITY_CSV,
    QUALITY_JSON,
    CANONICAL_SENSOR_COLUMNS,
    infer_column_mapping,
    predict_company_sensor_csv,
    sample_company_alias_dataframe,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def fail(message: str) -> None:
    raise AssertionError(message)


def pass_step(message: str) -> None:
    print(f"[OK] {message}")


def require_file(path: Path) -> None:
    if not path.exists():
        fail(f"Missing required file: {path}")


def verify_company_alias_csv() -> None:
    sample = sample_company_alias_dataframe()
    mapping_df = infer_column_mapping(sample)
    mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
    missing_mapping = [
        column
        for column in CANONICAL_SENSOR_COLUMNS
        if column != "Type" and not mapping.get(column)
    ]
    if missing_mapping:
        fail(f"Auto mapping failed for company-style sample: {missing_mapping}")

    result = predict_company_sensor_csv(
        sample,
        mapping=mapping,
        unit_conversions={
            "Air temperature [K]": "Auto",
            "Process temperature [K]": "Auto",
            "Rotational speed [rpm]": "No conversion",
            "Torque [Nm]": "No conversion",
            "Tool wear [min]": "No conversion",
        },
        policy_id="balanced",
        write_outputs=True,
    )
    result_df = result["result_df"]
    required_columns = [
        "raw_probability",
        "calibrated_probability",
        "risk_status",
        "risk_priority_score",
        "recommendation",
    ]
    missing_columns = [column for column in required_columns if column not in result_df.columns]
    if missing_columns:
        fail(f"Prediction result is missing columns: {missing_columns}")
    if result_df["calibrated_probability"].isna().any():
        fail("Calibrated probabilities contain missing values.")
    if not result["quality_report"]["applied_unit_conversions"]["Air temperature [K]"] == "Celsius -> Kelvin":
        fail("Auto unit detection should convert company Celsius air temperature to Kelvin.")
    pass_step("Company-style CSV auto mapping, unit conversion, and prediction passed.")


def verify_quality_edge_cases() -> None:
    bad_numeric = sample_company_alias_dataframe()
    bad_numeric["rpm"] = bad_numeric["rpm"].astype(object)
    bad_numeric.loc[1, "rpm"] = "not-a-number"
    mapping_df = infer_column_mapping(bad_numeric)
    mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
    result = predict_company_sensor_csv(
        bad_numeric,
        mapping=mapping,
        unit_conversions={column: "Auto" for column in CANONICAL_SENSOR_COLUMNS if column != "Type"},
        policy_id="precision_first",
        write_outputs=False,
    )
    issues = set(result["quality_df"]["issue"].astype(str))
    if "numeric_conversion_failed" not in issues:
        fail("Numeric conversion failure should be reported as a quality issue.")

    bad_type = sample_company_alias_dataframe()
    bad_type.loc[0, "product_grade"] = "UNKNOWN"
    mapping_df = infer_column_mapping(bad_type)
    mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
    result = predict_company_sensor_csv(
        bad_type,
        mapping=mapping,
        unit_conversions={column: "Auto" for column in CANONICAL_SENSOR_COLUMNS if column != "Type"},
        policy_id="recall_first",
        write_outputs=False,
    )
    issues = set(result["quality_df"]["issue"].astype(str))
    if "invalid_type" not in issues:
        fail("Invalid Type values should be reported as a quality issue.")
    pass_step("Missing/numeric/type quality edge cases passed.")


def verify_output_artifacts() -> None:
    required_files = [
        QUALITY_CSV,
        QUALITY_JSON,
        PREPROCESSING_MD,
        CALIBRATION_JSON,
        CALIBRATION_PNG,
        CONFIDENCE_MD,
        POLICY_JSON,
        PREDICTIONS_CSV,
        PRIORITY_CSV,
        POLICY_MD,
    ]
    for path in required_files:
        require_file(path)

    predictions = pd.read_csv(PREDICTIONS_CSV)
    priority = pd.read_csv(PRIORITY_CSV)
    if len(predictions) != len(priority):
        fail("Prediction and priority queue row counts should match.")
    if "risk_priority_score" not in priority.columns:
        fail("Priority queue is missing risk_priority_score.")

    calibration = json.loads(CALIBRATION_JSON.read_text(encoding="utf-8"))
    if calibration.get("selected_method") not in {"raw", "sigmoid", "isotonic"}:
        fail("Calibration selected_method is invalid.")

    policy = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
    for policy_id in ["precision_first", "balanced", "recall_first"]:
        if policy_id not in policy.get("policies", {}):
            fail(f"Missing operating policy threshold: {policy_id}")

    guardrail_text = PREPROCESSING_MD.read_text(encoding="utf-8") + CONFIDENCE_MD.read_text(encoding="utf-8")
    if "does not prove real company-data model performance" not in guardrail_text:
        fail("Preprocessing/confidence reports need a company-performance guardrail.")
    pass_step("Smart preprocessing/prediction output artifacts passed.")


def main() -> None:
    print(f"Verifying smart preprocessing prediction engine at: {PROJECT_ROOT}")
    verify_company_alias_csv()
    verify_quality_edge_cases()
    verify_output_artifacts()
    print("All smart preprocessing prediction engine checks passed.")


if __name__ == "__main__":
    main()
