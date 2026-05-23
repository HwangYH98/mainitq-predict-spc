from __future__ import annotations

import pandas as pd
from preprocessing_prediction_engine import (
    infer_column_mapping,
    predict_company_sensor_csv,
    sample_company_alias_dataframe,
)


def test_smart_company_csv_prediction_outputs_priority_scores() -> None:
    sample = sample_company_alias_dataframe()
    mapping_df = infer_column_mapping(sample)
    mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
    units = {
        "Air temperature [K]": "Auto",
        "Process temperature [K]": "Auto",
        "Rotational speed [rpm]": "No conversion",
        "Torque [Nm]": "No conversion",
        "Tool wear [min]": "No conversion",
    }

    result = predict_company_sensor_csv(
        sample,
        mapping=mapping,
        unit_conversions=units,
        policy_id="balanced",
        write_outputs=False,
    )

    result_df = result["result_df"]
    priority_df = result["priority_df"]
    assert len(result_df) == len(sample)
    assert {"raw_probability", "calibrated_probability", "risk_priority_score", "recommendation"}.issubset(
        result_df.columns
    )
    assert priority_df["risk_priority_score"].is_monotonic_decreasing


def test_missing_required_mapping_is_flagged_in_quality_report() -> None:
    result = predict_company_sensor_csv(pd.DataFrame({"unknown": [1, 2, 3]}), write_outputs=False)
    quality_df = result["quality_df"]
    assert "missing_column" in set(quality_df["issue"])
    assert result["quality_report"]["quality_status"] in {"Review Needed", "Low Confidence", "Low"}
