from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

DEFAULT_FIELD_DATA = OUTPUT_DIR / "field_data_template.csv"
DEFAULT_COST_DATA = OUTPUT_DIR / "field_cost_template.csv"

REPORT_CSV = OUTPUT_DIR / "field_validation_report.csv"
REPORT_JSON = OUTPUT_DIR / "field_validation_report.json"
REPORT_MD = OUTPUT_DIR / "field_validation_report.md"
REPORT_ZIP = OUTPUT_DIR / "field_validation_report_bundle.zip"

FIELD_REQUIRED_COLUMNS = {
    "equipment_id",
    "timestamp",
    "air_temperature_k",
    "process_temperature_k",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
    "actual_failure",
}

COST_REQUIRED_COLUMNS = {
    "work_order_id",
    "downtime_minutes",
    "parts_cost",
    "labor_cost",
    "lost_production_cost",
    "false_alarm",
    "missed_failure",
}

MAINTENANCE_RECOMMENDED_COLUMNS = {
    "work_order_id",
    "equipment_id",
    "maintenance_start",
    "maintenance_end",
    "maintenance_action_type",
}


def _require_columns(df: pd.DataFrame, required: set[str], source_name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{source_name} is missing required columns: {', '.join(missing)}")


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator == 0 or math.isnan(denominator):
        return 0.0
    return float(numerator / denominator)


def _classification_metrics(actual_failure: pd.Series, predicted_alert: pd.Series) -> dict[str, float | int]:
    actual = actual_failure.astype(int).to_numpy()
    predicted = predicted_alert.astype(int).to_numpy()
    tp = int(((actual == 1) & (predicted == 1)).sum())
    fp = int(((actual == 0) & (predicted == 1)).sum())
    fn = int(((actual == 1) & (predicted == 0)).sum())
    tn = int(((actual == 0) & (predicted == 0)).sum())
    precision = _safe_rate(tp, tp + fp)
    recall = _safe_rate(tp, tp + fn)
    f1 = _safe_rate(2 * precision * recall, precision + recall)
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1_score": round(f1, 6),
        "false_alarm_count": fp,
        "missed_failure_count": fn,
    }


def _lead_time_metrics(field_df: pd.DataFrame, result_df: pd.DataFrame) -> dict[str, float | int | None]:
    if "failure_timestamp" not in field_df.columns:
        return {"lead_time_minutes_mean": None, "early_warning_rate": 0.0, "lead_time_events": 0}

    merged = field_df.copy()
    merged["predicted_alert"] = result_df["risk_status"].eq("High Risk").to_numpy()
    merged["timestamp"] = pd.to_datetime(merged["timestamp"], errors="coerce", utc=True)
    merged["failure_timestamp"] = pd.to_datetime(merged["failure_timestamp"], errors="coerce", utc=True)

    lead_times: list[float] = []
    failure_groups = merged[merged["actual_failure"].astype(int) == 1].groupby("equipment_id", dropna=False)
    for _, group in failure_groups:
        failure_time = group["failure_timestamp"].dropna().min()
        if pd.isna(failure_time):
            continue
        alerts = group[(group["predicted_alert"]) & (group["timestamp"].notna()) & (group["timestamp"] <= failure_time)]
        if alerts.empty:
            continue
        first_alert = alerts["timestamp"].min()
        lead_times.append(float((failure_time - first_alert).total_seconds() / 60.0))

    failure_count = int((merged["actual_failure"].astype(int) == 1).sum())
    early_warning_rate = _safe_rate(len(lead_times), failure_count)
    mean_lead_time = round(float(np.mean(lead_times)), 3) if lead_times else None
    return {
        "lead_time_minutes_mean": mean_lead_time,
        "early_warning_rate": round(early_warning_rate, 6),
        "lead_time_events": len(lead_times),
    }


def _cost_metrics(cost_df: pd.DataFrame) -> dict[str, Any]:
    cost_components = ["parts_cost", "labor_cost", "lost_production_cost"]
    numeric_cost = cost_df.copy()
    optional_numeric_columns = [
        "baseline_total_cost",
        "new_policy_total_cost",
        "baseline_downtime_minutes",
        "new_policy_downtime_minutes",
        "baseline_detection_delay_minutes",
        "new_policy_detection_delay_minutes",
    ]
    for column in cost_components + ["downtime_minutes"] + optional_numeric_columns:
        if column not in numeric_cost.columns:
            continue
        numeric_cost[column] = pd.to_numeric(numeric_cost[column], errors="coerce").fillna(0)

    component_total = float(numeric_cost[cost_components].sum(axis=1).sum())
    downtime_total = float(numeric_cost["downtime_minutes"].sum())
    false_alarm_count = int(pd.to_numeric(numeric_cost["false_alarm"], errors="coerce").fillna(0).sum())
    missed_failure_count = int(pd.to_numeric(numeric_cost["missed_failure"], errors="coerce").fillna(0).sum())

    has_direct_cost = {"baseline_total_cost", "new_policy_total_cost"}.issubset(numeric_cost.columns)
    if has_direct_cost:
        baseline_cost = float(numeric_cost["baseline_total_cost"].sum())
        new_policy_cost = float(numeric_cost["new_policy_total_cost"].sum())
        cost_source = "direct_before_after_cost_fields"
    else:
        baseline_cost = component_total
        new_policy_cost = component_total
        cost_source = "component_cost_trace_only"

    has_direct_downtime = {"baseline_downtime_minutes", "new_policy_downtime_minutes"}.issubset(numeric_cost.columns)
    if has_direct_downtime:
        baseline_downtime = float(numeric_cost["baseline_downtime_minutes"].sum())
        new_policy_downtime = float(numeric_cost["new_policy_downtime_minutes"].sum())
        downtime_source = "direct_before_after_downtime_fields"
        downtime_delta_rate = _safe_rate(baseline_downtime - new_policy_downtime, baseline_downtime)
    else:
        baseline_downtime = None
        new_policy_downtime = None
        downtime_source = "downtime_trace_only"
        downtime_delta_rate = None

    has_direct_detection = {
        "baseline_detection_delay_minutes",
        "new_policy_detection_delay_minutes",
    }.issubset(numeric_cost.columns)
    if has_direct_detection:
        baseline_detection_delay = float(numeric_cost["baseline_detection_delay_minutes"].sum())
        new_policy_detection_delay = float(numeric_cost["new_policy_detection_delay_minutes"].sum())
        detection_time_source = "direct_before_after_detection_delay_fields"
        detection_time_delta_rate = _safe_rate(
            baseline_detection_delay - new_policy_detection_delay,
            baseline_detection_delay,
        )
    else:
        baseline_detection_delay = None
        new_policy_detection_delay = None
        detection_time_source = "detection_delay_trace_missing"
        detection_time_delta_rate = None

    return {
        "downtime_minutes_total": round(downtime_total, 3),
        "baseline_downtime_minutes": round(baseline_downtime, 3) if baseline_downtime is not None else None,
        "new_policy_downtime_minutes": round(new_policy_downtime, 3) if new_policy_downtime is not None else None,
        "downtime_delta_rate": round(downtime_delta_rate, 6) if downtime_delta_rate is not None else None,
        "downtime_source": downtime_source,
        "baseline_detection_delay_minutes": (
            round(baseline_detection_delay, 3) if baseline_detection_delay is not None else None
        ),
        "new_policy_detection_delay_minutes": (
            round(new_policy_detection_delay, 3) if new_policy_detection_delay is not None else None
        ),
        "detection_time_delta_rate": (
            round(detection_time_delta_rate, 6) if detection_time_delta_rate is not None else None
        ),
        "detection_time_source": detection_time_source,
        "maintenance_component_cost": round(component_total, 3),
        "baseline_cost": round(baseline_cost, 3),
        "new_policy_cost": round(new_policy_cost, 3),
        "maintenance_cost_delta_rate": round(_safe_rate(baseline_cost - new_policy_cost, baseline_cost), 6),
        "cost_source": cost_source,
        "cost_false_alarm_count": false_alarm_count,
        "cost_missed_failure_count": missed_failure_count,
    }


def _maintenance_metrics(maintenance_data_path: Path | None) -> dict[str, Any]:
    if maintenance_data_path is None or not maintenance_data_path.exists():
        return {
            "maintenance_rows": 0,
            "maintenance_source": "maintenance_log_missing",
            "maintenance_schema_status": "missing",
        }
    maintenance_df = pd.read_csv(maintenance_data_path)
    missing = sorted(MAINTENANCE_RECOMMENDED_COLUMNS - set(maintenance_df.columns))
    return {
        "maintenance_rows": int(len(maintenance_df)),
        "maintenance_source": str(maintenance_data_path),
        "maintenance_schema_status": "ok" if not missing else "partial",
        "maintenance_missing_columns": ", ".join(missing),
    }


def _prediction_input_from_field_data(field_df: pd.DataFrame) -> pd.DataFrame:
    product_type = field_df["product_type"] if "product_type" in field_df.columns else "M"
    return pd.DataFrame(
        {
            "Type": product_type,
            "Air temperature [K]": field_df["air_temperature_k"],
            "Process temperature [K]": field_df["process_temperature_k"],
            "Rotational speed [rpm]": field_df["rotational_speed_rpm"],
            "Torque [Nm]": field_df["torque_nm"],
            "Tool wear [min]": field_df["tool_wear_min"],
        }
    )


def _prediction_metrics_from_field_data(field_df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    _require_columns(field_df, FIELD_REQUIRED_COLUMNS, "field data")
    actual_failure = pd.to_numeric(field_df["actual_failure"], errors="coerce")
    if actual_failure.isna().any():
        raise ValueError("field data actual_failure column must contain 0/1 labels for field validation")

    from preprocessing_prediction_engine import predict_company_sensor_csv

    prediction_input = _prediction_input_from_field_data(field_df)
    mapping = {column: column for column in prediction_input.columns}
    prediction = predict_company_sensor_csv(
        prediction_input,
        mapping=mapping,
        unit_conversions={column: "No conversion" for column in mapping},
        policy_id="balanced",
        write_outputs=False,
    )
    result_df = prediction["result_df"]
    predicted_alert = result_df["risk_status"].eq("High Risk")
    metrics = {
        **_classification_metrics(actual_failure, predicted_alert),
        **_lead_time_metrics(field_df.assign(actual_failure=actual_failure.astype(int)), result_df),
    }
    return metrics, result_df


def _write_report(metrics: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / REPORT_CSV.name
    json_path = output_dir / REPORT_JSON.name
    md_path = output_dir / REPORT_MD.name
    pd.DataFrame([metrics]).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_render_markdown(metrics), encoding="utf-8")
    zip_path = create_field_validation_export_zip(output_dir)
    metrics["report_csv"] = str(csv_path)
    metrics["report_json"] = str(json_path)
    metrics["report_md"] = str(md_path)
    metrics["report_zip"] = str(zip_path)
    return metrics


def evaluate_field_validation(
    field_data_path: Path = DEFAULT_FIELD_DATA,
    cost_data_path: Path = DEFAULT_COST_DATA,
    output_dir: Path = OUTPUT_DIR,
    source_mode_override: str | None = None,
    maintenance_data_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate a labeled field-data package and write a validation report."""
    if not field_data_path.exists():
        raise FileNotFoundError(f"field data file was not found: {field_data_path}")
    if not cost_data_path.exists():
        raise FileNotFoundError(f"field cost file was not found: {cost_data_path}")

    field_df = pd.read_csv(field_data_path)
    cost_df = pd.read_csv(cost_data_path)
    _require_columns(field_df, FIELD_REQUIRED_COLUMNS, "field data")
    _require_columns(cost_df, COST_REQUIRED_COLUMNS, "field cost data")
    source_mode = source_mode_override or (
        "template_demo"
        if field_data_path.resolve() == DEFAULT_FIELD_DATA.resolve()
        and cost_data_path.resolve() == DEFAULT_COST_DATA.resolve()
        else "company_field_logs"
    )

    if len(cost_df) == 0:
        raise ValueError("field cost data is empty; cost and downtime validation cannot be generated")

    prediction_metrics, _ = _prediction_metrics_from_field_data(field_df)
    has_direct_cost = {"baseline_total_cost", "new_policy_total_cost"}.issubset(cost_df.columns)
    has_direct_downtime = {"baseline_downtime_minutes", "new_policy_downtime_minutes"}.issubset(cost_df.columns)
    has_direct_detection = {
        "baseline_detection_delay_minutes",
        "new_policy_detection_delay_minutes",
    }.issubset(cost_df.columns)
    if source_mode == "template_demo":
        claim_status = "template_demo_not_field_proof"
    elif has_direct_cost and has_direct_downtime and has_direct_detection:
        claim_status = "field_validation_ready"
    elif has_direct_cost and has_direct_downtime:
        claim_status = "cost_and_downtime_validation_ready_detection_claim_not_supported"
    elif has_direct_cost:
        claim_status = "cost_validation_ready_downtime_claim_not_supported"
    elif has_direct_downtime:
        claim_status = "downtime_validation_ready_cost_claim_not_supported"
    else:
        claim_status = "prediction_quality_only_cost_and_downtime_claim_not_supported"
    cost_metrics = _cost_metrics(cost_df)
    claim_flags = _claim_flags(source_mode, claim_status, cost_metrics)
    metrics = {
        "source_mode": source_mode,
        "field_data_rows": int(len(field_df)),
        "cost_rows": int(len(cost_df)),
        **prediction_metrics,
        **cost_metrics,
        **_maintenance_metrics(maintenance_data_path),
        **claim_flags,
        "claim_status": claim_status,
        "field_data_path": str(field_data_path),
        "cost_data_path": str(cost_data_path),
        "maintenance_data_path": str(maintenance_data_path) if maintenance_data_path else "",
    }

    return _write_report(metrics, output_dir)


def evaluate_field_validation_package(
    field_data_path: Path,
    cost_data_path: Path | None = None,
    output_dir: Path = OUTPUT_DIR,
    source_mode_override: str | None = None,
    maintenance_data_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate whatever field-validation evidence is available and write a guarded report."""
    if not field_data_path.exists():
        raise FileNotFoundError(f"field data file was not found: {field_data_path}")

    if cost_data_path and cost_data_path.exists():
        return evaluate_field_validation(
            field_data_path,
            cost_data_path,
            output_dir,
            source_mode_override,
            maintenance_data_path=maintenance_data_path,
        )

    field_df = pd.read_csv(field_data_path)
    prediction_metrics, _ = _prediction_metrics_from_field_data(field_df)
    source_mode = source_mode_override or "company_field_logs_partial"
    metrics = {
        "source_mode": source_mode,
        "field_data_rows": int(len(field_df)),
        "cost_rows": 0,
        **prediction_metrics,
        **_maintenance_metrics(maintenance_data_path),
        "downtime_minutes_total": None,
        "maintenance_component_cost": None,
        "baseline_cost": None,
        "new_policy_cost": None,
        "maintenance_cost_delta_rate": None,
        "baseline_downtime_minutes": None,
        "new_policy_downtime_minutes": None,
        "downtime_delta_rate": None,
        "downtime_source": "cost_log_missing",
        "baseline_detection_delay_minutes": None,
        "new_policy_detection_delay_minutes": None,
        "detection_time_delta_rate": None,
        "detection_time_source": "cost_log_missing",
        "cost_source": "cost_log_missing",
        "cost_false_alarm_count": None,
        "cost_missed_failure_count": None,
        "claim_status": (
            "performance_and_traceability_only_cost_claim_not_supported"
            if maintenance_data_path and maintenance_data_path.exists()
            else "performance_recheck_only_cost_and_downtime_claim_not_supported"
        ),
        "field_data_path": str(field_data_path),
        "cost_data_path": str(cost_data_path) if cost_data_path else "",
        "maintenance_data_path": str(maintenance_data_path) if maintenance_data_path else "",
    }
    metrics.update(_claim_flags(source_mode, metrics["claim_status"], metrics))
    return _write_report(metrics, output_dir)


def _claim_flags(source_mode: str, claim_status: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """Return explicit booleans for field claims so wording cannot overreach."""
    is_company_log = source_mode != "template_demo"
    cost_allowed = (
        is_company_log
        and metrics.get("maintenance_cost_delta_rate") is not None
        and metrics.get("cost_source") == "direct_before_after_cost_fields"
    )
    downtime_allowed = (
        is_company_log
        and metrics.get("downtime_delta_rate") is not None
        and metrics.get("downtime_source") == "direct_before_after_downtime_fields"
    )
    detection_allowed = (
        is_company_log
        and metrics.get("detection_time_delta_rate") is not None
        and metrics.get("detection_time_source") == "direct_before_after_detection_delay_fields"
    )
    allowed: list[str] = []
    blocked: list[str] = []
    if cost_allowed:
        allowed.append("actual cost reduction")
    else:
        blocked.append("actual cost reduction")
    if downtime_allowed:
        allowed.append("actual downtime reduction")
    else:
        blocked.append("actual downtime reduction")
    if detection_allowed:
        allowed.append("actual detection-time reduction")
    else:
        blocked.append("actual detection-time reduction")
    return {
        "cost_reduction_claim_allowed": bool(cost_allowed),
        "downtime_reduction_claim_allowed": bool(downtime_allowed),
        "detection_time_reduction_claim_allowed": bool(detection_allowed),
        "field_claim_ready": bool(cost_allowed and downtime_allowed and detection_allowed),
        "allowed_claims": ", ".join(allowed) if allowed else "none",
        "blocked_claims": ", ".join(blocked) if blocked else "none",
        "claim_gate_note": (
            "All direct company before/after fields are present."
            if cost_allowed and downtime_allowed and detection_allowed
            else "Some direct company before/after fields are missing or this is template/sample data."
        ),
    }


def create_field_validation_export_zip(output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / REPORT_ZIP.name
    report_files = [
        output_dir / REPORT_MD.name,
        output_dir / REPORT_CSV.name,
        output_dir / REPORT_JSON.name,
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for report_file in report_files:
            if report_file.exists():
                archive.write(report_file, arcname=report_file.name)
    return zip_path


def _render_markdown(metrics: dict[str, Any]) -> str:
    claim_status = str(metrics.get("claim_status", ""))
    claim_notes = {
        "template_demo_not_field_proof": "Template/sample data only. Do not claim field performance, cost, or lead-time impact.",
        "field_validation_ready": "Company field logs include direct before/after cost and downtime fields. Report computed metrics with the equipment group and period used.",
        "cost_and_downtime_validation_ready_detection_claim_not_supported": "Direct before/after cost and downtime fields are present, but detection-time reduction is not supported without direct before/after detection-delay fields.",
        "cost_validation_ready_downtime_claim_not_supported": "Direct before/after cost fields are present, but actual downtime reduction is not supported without direct before/after downtime fields.",
        "downtime_validation_ready_cost_claim_not_supported": "Direct before/after downtime fields are present, but actual cost reduction is not supported without direct before/after cost fields.",
        "prediction_quality_only_cost_and_downtime_claim_not_supported": "Prediction metrics are available, but actual cost and downtime reduction are not supported without direct before/after fields.",
        "performance_recheck_only_cost_and_downtime_claim_not_supported": "Label-based performance can be rechecked, but cost and downtime impact cannot be claimed without cost logs.",
        "performance_and_traceability_only_cost_claim_not_supported": "Label-based performance and maintenance traceability can be reviewed, but cost and downtime impact cannot be claimed without cost logs.",
    }
    rows = [
        "# Field Validation Report",
        "",
        "This report is generated only when labeled field data and cost logs are available.",
        "It is not a substitute for a controlled before/after field study.",
        f"Source mode: `{metrics.get('source_mode')}`.",
        f"Claim status: `{metrics.get('claim_status')}`.",
        f"Claim interpretation: {claim_notes.get(claim_status, 'Review input coverage before making operational claims.')}",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in [
        "field_data_rows",
        "cost_rows",
        "maintenance_rows",
        "maintenance_schema_status",
        "source_mode",
        "precision",
        "recall",
        "f1_score",
        "false_alarm_count",
        "missed_failure_count",
        "lead_time_minutes_mean",
        "early_warning_rate",
        "downtime_minutes_total",
        "baseline_downtime_minutes",
        "new_policy_downtime_minutes",
        "downtime_delta_rate",
        "baseline_detection_delay_minutes",
        "new_policy_detection_delay_minutes",
        "detection_time_delta_rate",
        "baseline_cost",
        "new_policy_cost",
        "maintenance_cost_delta_rate",
        "cost_reduction_claim_allowed",
        "downtime_reduction_claim_allowed",
        "detection_time_reduction_claim_allowed",
        "field_claim_ready",
        "allowed_claims",
        "blocked_claims",
    ]:
        rows.append(f"| {key} | {metrics.get(key)} |")
    rows.extend(
        [
            "",
            "## Claim Guardrail",
            "",
            "- Actual field cost reduction can be claimed only when the company provides complete before/after cost logs.",
            "- Actual downtime reduction can be claimed only when baseline_downtime_minutes and new_policy_downtime_minutes are both present.",
            "- Actual lead-time improvement can be claimed only when baseline detection timing and new-policy alert timing are traceable for the same equipment and period.",
            "- Actual detection-time reduction can be claimed only when baseline_detection_delay_minutes and new_policy_detection_delay_minutes are both present.",
            "- Alert lead time can be reported when failure timestamps and first alert timestamps are traceable, but reduction claims still need a baseline.",
            "- Maintenance history improves traceability, but it does not prove cost impact without downtime/cost logs.",
            "- If direct baseline/new-policy cost, downtime, or detection-delay fields are missing, use this report for prediction and traceability checks only.",
        ]
    )
    return "\n".join(rows) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a field validation report from labeled company data and cost logs.")
    parser.add_argument("--field-data", type=Path, default=DEFAULT_FIELD_DATA)
    parser.add_argument("--cost-data", type=Path, default=None)
    parser.add_argument("--maintenance-data", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    raw_args = argv if argv is not None else sys.argv[1:]
    args = parse_args(raw_args)
    cost_data_was_provided = "--cost-data" in raw_args
    if not raw_args:
        metrics = evaluate_field_validation(
            args.field_data,
            DEFAULT_COST_DATA,
            args.output_dir,
            maintenance_data_path=args.maintenance_data,
        )
    elif cost_data_was_provided and args.cost_data is not None:
        metrics = evaluate_field_validation(
            args.field_data,
            args.cost_data,
            args.output_dir,
            maintenance_data_path=args.maintenance_data,
        )
    else:
        metrics = evaluate_field_validation_package(
            args.field_data,
            cost_data_path=None,
            output_dir=args.output_dir,
            maintenance_data_path=args.maintenance_data,
        )
    print("Field validation report created successfully.")
    print(f"claim_status: {metrics['claim_status']}")
    print(f"precision: {metrics['precision']}")
    print(f"recall: {metrics['recall']}")
    print(f"cost_delta_rate: {metrics['maintenance_cost_delta_rate']}")
    print(f"downtime_delta_rate: {metrics['downtime_delta_rate']}")
    print(f"detection_time_delta_rate: {metrics['detection_time_delta_rate']}")
    print(f"field_claim_ready: {metrics['field_claim_ready']}")
    print(f"report_csv: {metrics['report_csv']}")
    print(f"report_md: {metrics['report_md']}")
    print(f"report_zip: {metrics['report_zip']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
