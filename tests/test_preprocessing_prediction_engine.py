from __future__ import annotations

import pandas as pd
from preprocessing_prediction_engine import (
    CANONICAL_SENSOR_COLUMNS,
    infer_column_mapping,
    NUMERIC_SENSOR_COLUMNS,
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


def test_korean_company_column_mapping_supports_plain_and_spaced_names() -> None:
    samples = [
        pd.DataFrame(
            {
                "제품등급": ["L", "M", "H"],
                "공기온도": [25.0, 26.1, 30.2],
                "공정온도": [35.4, 36.6, 39.8],
                "회전속도": [1551, 1408, 1320],
                "토크": [42.8, 46.3, 58.2],
                "공구마모": [0, 3, 120],
            }
        ),
        pd.DataFrame(
            {
                "제품 등급": ["L", "M", "H"],
                "공기 온도": [25.0, 26.1, 30.2],
                "공정 온도": [35.4, 36.6, 39.8],
                "회전 속도": [1551, 1408, 1320],
                "모터 토크": [42.8, 46.3, 58.2],
                "공구 마모 시간": [0, 3, 120],
            }
        ),
    ]

    for sample in samples:
        mapping_df = infer_column_mapping(sample)
        mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
        assert all(mapping[column] for column in CANONICAL_SENSOR_COLUMNS)

        result = predict_company_sensor_csv(
            sample,
            mapping=mapping,
            unit_conversions={column: "Auto" for column in NUMERIC_SENSOR_COLUMNS},
            policy_id="balanced",
            write_outputs=False,
        )

        missing_required = result["quality_df"][
            (result["quality_df"]["issue"] == "missing_column")
            & (result["quality_df"]["canonical_column"].isin(CANONICAL_SENSOR_COLUMNS))
        ]
        assert missing_required.empty
        assert len(result["result_df"]) == len(sample)
        assert {"calibrated_probability", "risk_status", "recommendation"}.issubset(result["result_df"].columns)
