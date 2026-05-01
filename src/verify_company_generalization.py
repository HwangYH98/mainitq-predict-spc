import argparse
import json
from pathlib import Path

import pandas as pd

from company_adapter import (
    UNIT_PRESETS,
    save_custom_training_outputs,
    train_custom_company_model,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "custom_company_model"

REQUIRED_MODEL_NAMES = ["logistic_regression", "xgboost"]
REQUIRED_METRIC_KEYS = ["precision", "recall", "f1_score", "roc_auc", "pr_auc"]

DEMO_ID_TIME_COLUMNS = ["asset_id", "event_time"]
DEMO_TARGET_COLUMN = "quality_result"
DEMO_UNIT_CONVERSIONS = {
    "air_temp_celsius": {
        "preset": "Celsius -> Kelvin",
        "multiplier": 1.0,
        "offset": 273.15,
    },
    "process_temp_celsius": {
        "preset": "Celsius -> Kelvin",
        "multiplier": 1.0,
        "offset": 273.15,
    },
}


def pass_step(message: str) -> None:
    print(f"[OK] {message}")


def require_file(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"Missing required file: {path}")
    if path.is_file() and path.stat().st_size <= 0:
        raise AssertionError(f"File is empty: {path}")


def comma_list(value: str | None) -> list[str]:
    """Parse a comma-separated CLI value into clean column names."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_unit_conversion(value: str) -> tuple[str, dict]:
    """
    Parse one --unit-conversion option.

    Supported forms:
    - column=Preset Name
    - column=multiplier,offset
    """
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            "--unit-conversion must look like column=Preset Name or column=multiplier,offset."
        )

    column_name, conversion_text = [part.strip() for part in value.split("=", 1)]
    if not column_name:
        raise argparse.ArgumentTypeError("Unit conversion column name cannot be empty.")
    if not conversion_text:
        raise argparse.ArgumentTypeError("Unit conversion value cannot be empty.")

    if conversion_text in UNIT_PRESETS:
        preset = UNIT_PRESETS[conversion_text]
        return column_name, {
            "preset": conversion_text,
            "multiplier": float(preset["multiplier"]),
            "offset": float(preset["offset"]),
        }

    pieces = [piece.strip() for piece in conversion_text.split(",")]
    if len(pieces) != 2:
        raise argparse.ArgumentTypeError(
            "Custom unit conversion must look like column=multiplier,offset."
        )

    try:
        multiplier = float(pieces[0])
        offset = float(pieces[1])
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Custom unit conversion multiplier and offset must be numbers."
        ) from error

    return column_name, {
        "preset": "Custom",
        "multiplier": multiplier,
        "offset": offset,
    }


def parse_unit_conversions(values: list[str] | None) -> dict[str, dict]:
    conversions = {}
    for value in values or []:
        column_name, conversion = parse_unit_conversion(value)
        conversions[column_name] = conversion
    return conversions


def build_demo_company_csv() -> pd.DataFrame:
    """Rename AI4I into a fake company schema to test mapping and unit conversion."""
    ai4i = pd.read_csv(DATA_PATH)
    return pd.DataFrame(
        {
            "asset_id": ai4i["UDI"],
            "event_time": pd.date_range("2026-01-01", periods=len(ai4i), freq="min"),
            "product_family": ai4i["Type"],
            "air_temp_celsius": ai4i["Air temperature [K]"] - 273.15,
            "process_temp_celsius": ai4i["Process temperature [K]"] - 273.15,
            "spindle_speed": ai4i["Rotational speed [rpm]"],
            "load_torque": ai4i["Torque [Nm]"],
            "tool_age_min": ai4i["Tool wear [min]"],
            "quality_result": ai4i["Machine failure"].map({0: "ok", 1: "failure"}),
        }
    )


def load_company_dataframe(args: argparse.Namespace) -> tuple[pd.DataFrame, str, list[str], dict, list[str]]:
    """Return the DataFrame and mapping choices for Stage 14 verification."""
    if args.csv_path:
        csv_path = Path(args.csv_path)
        require_file(csv_path)
        if not args.target_column:
            raise ValueError("--target-column is required when --csv-path is provided.")

        company_df = pd.read_csv(csv_path)
        target_column = args.target_column
        id_time_columns = comma_list(args.id_time_columns)
        unit_conversions = parse_unit_conversions(args.unit_conversion)
        pass_step(f"Company CSV loaded from {csv_path} ({len(company_df)} rows).")
        return company_df, target_column, id_time_columns, unit_conversions, []

    require_file(DATA_PATH)
    demo_df = build_demo_company_csv()
    pass_step(f"Demo company CSV prepared from AI4I ({len(demo_df)} rows).")
    return (
        demo_df,
        DEMO_TARGET_COLUMN,
        DEMO_ID_TIME_COLUMNS,
        DEMO_UNIT_CONVERSIONS,
        ["air_temp_celsius", "process_temp_celsius"],
    )


def verify_saved_outputs(
    paths: dict[str, str],
    result: dict,
    expected_numeric_columns: list[str] | None = None,
) -> None:
    for path_text in paths.values():
        require_file(Path(path_text))

    metrics = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))
    if metrics["source"] != "custom_company_csv":
        raise AssertionError("custom_metrics.json source is incorrect.")
    if metrics["test_rows"] <= 0:
        raise AssertionError("custom_metrics.json test_rows must be greater than zero.")

    for model_name in REQUIRED_MODEL_NAMES:
        model_metrics = metrics["models"].get(model_name)
        if model_metrics is None:
            raise AssertionError(f"custom_metrics.json is missing {model_name} metrics.")
        missing_keys = [
            key for key in REQUIRED_METRIC_KEYS if key not in model_metrics
        ]
        if missing_keys:
            raise AssertionError(f"{model_name} metrics are missing keys: {missing_keys}")

    feature_schema = json.loads(Path(paths["feature_schema"]).read_text(encoding="utf-8"))
    if not feature_schema.get("encoded_feature_columns"):
        raise AssertionError("feature_schema.json has no encoded feature columns.")

    for column_name in expected_numeric_columns or []:
        if column_name not in feature_schema["numeric_columns"]:
            raise AssertionError(
                f"feature_schema.json did not preserve numeric column: {column_name}"
            )

    threshold_summary = json.loads(Path(paths["threshold_summary"]).read_text(encoding="utf-8"))
    for key in ["selected_threshold", "selected_metrics", "default_0_5_metrics"]:
        if key not in threshold_summary:
            raise AssertionError(f"custom_threshold_summary.json is missing key: {key}")

    predictions = pd.read_csv(paths["predictions"])
    if len(predictions) != int(metrics["test_rows"]):
        raise AssertionError("custom_predictions.csv row count does not match custom_metrics.json.")
    for column in [
        "xgboost_probability",
        "xgboost_prediction_by_selected_threshold",
        "risk_status",
    ]:
        if column not in predictions.columns:
            raise AssertionError(f"custom_predictions.csv is missing column: {column}")

    pass_step(
        "Saved Stage 14 outputs passed "
        f"({len(predictions)} predictions, {len(feature_schema['encoded_feature_columns'])} features)."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 14-lite company CSV retraining verification. "
            "Without --csv-path, a reproducible AI4I-derived demo company CSV is used."
        )
    )
    parser.add_argument(
        "--csv-path",
        help="Optional labeled company CSV path. If omitted, the AI4I demo-company CSV is used.",
    )
    parser.add_argument(
        "--target-column",
        help="Target column in the real company CSV. Required with --csv-path.",
    )
    parser.add_argument(
        "--id-time-columns",
        default="",
        help="Comma-separated ID/time columns to preserve but exclude from training.",
    )
    parser.add_argument(
        "--unit-conversion",
        action="append",
        default=[],
        help=(
            "Optional unit conversion, repeatable. Examples: "
            "\"temp_c=Celsius -> Kelvin\" or \"sensor_x=1.0,273.15\"."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Directory where Stage 14 custom-company outputs are saved.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(f"Verifying Stage 14-lite company retraining at: {PROJECT_ROOT}")
    company_df, target_column, id_time_columns, unit_conversions, expected_numeric_columns = (
        load_company_dataframe(args)
    )

    result = train_custom_company_model(
        company_df,
        target_column=target_column,
        id_time_columns=id_time_columns,
        unit_conversions=unit_conversions,
    )
    pass_step(
        "Stage 14 custom-company retraining passed "
        f"(best model: {result['metrics']['best_model_by_pr_auc']}, "
        f"threshold: {result['threshold_summary']['selected_threshold']})."
    )

    output_dir = Path(args.output_dir)
    paths = save_custom_training_outputs(result, output_dir)
    verify_saved_outputs(paths, result, expected_numeric_columns=expected_numeric_columns)
    print("All Stage 14-lite company retraining checks passed.")


if __name__ == "__main__":
    main()
