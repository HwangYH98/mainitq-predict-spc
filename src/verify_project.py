import importlib
import json
import py_compile
import sqlite3
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
APP_DIR = PROJECT_ROOT / "app"
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

REQUIRED_DATA_COLUMNS = [
    "UDI",
    "Product ID",
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
    "Machine failure",
    "TWF",
    "HDF",
    "PWF",
    "OSF",
    "RNF",
]

REQUIRED_METRIC_KEYS = ["precision", "recall", "f1_score", "roc_auc", "pr_auc"]

REQUIRED_BASELINE_OUTPUTS = [
    "metrics.json",
    "confusion_matrix.png",
    "pr_curve.png",
    "baseline_predictions.csv",
]

REQUIRED_EXTENDED_OUTPUTS = [
    "threshold_metrics.csv",
    "threshold_summary.json",
    "threshold_tuning.png",
    "shap_summary.png",
    "shap_bar.png",
    "local_case_explanation.md",
    "local_case_explanation.json",
    "presentation_summary.md",
    "research_plan_may11.md",
    "midterm_presentation_guide.md",
    "midterm_qna_may11.md",
    "rehearsal_checklist_may11.md",
    "presentation_day_backup_checklist.md",
    "final_stage_roadmap.md",
    "stage9_field_applicability.md",
    "stage10_operations_summary.md",
    "spc_timeseries.csv",
    "spc_summary.json",
    "spc_risk_chart.png",
    "spc_control_chart.png",
    "future_deviation_predictions.csv",
    "future_deviation_metrics.json",
    "future_deviation_chart.png",
    "ai_report_context.json",
    "ai_manager_report.md",
    "final_paper_outline.md",
    "final_presentation_plan.md",
]

REQUIRED_STAGE14_OUTPUTS = [
    "mapping.json",
    "feature_schema.json",
    "custom_metrics.json",
    "custom_threshold_summary.json",
    "custom_threshold_metrics.csv",
    "custom_predictions.csv",
    "xgboost_model.joblib",
    "logistic_model.joblib",
    "custom_shap_bar.png",
]

REQUIRED_STAGE15_18_OUTPUTS = [
    "operations.db",
    "stage15_20_architecture.md",
    "realtime_stream/latest_events.csv",
    "work_order_decisions.csv",
]

REQUIRED_COMPARISON_OUTPUTS = [
    "model_strategy_comparison.csv",
    "model_strategy_comparison.json",
    "model_strategy_pr_curve.png",
    "model_strategy_summary.md",
    "spc_vs_ml_comparison.csv",
    "spc_vs_ml_comparison.json",
    "spc_vs_ml_summary.md",
    "mock_field_bridge_summary.json",
    "mock_field_bridge_summary.md",
    "operational_value_simulation.csv",
    "operational_value_simulation.json",
    "operational_value_simulation.png",
    "operational_value_simulation.md",
    "product_capability_comparison.csv",
    "product_capability_comparison.md",
    "workflow_traceability_summary.csv",
    "workflow_traceability_summary.json",
    "workflow_traceability_summary.md",
    "thesis_evidence_pack.md",
    "company_input_quality_report.csv",
    "company_input_quality_report.json",
    "company_preprocessing_report.md",
    "probability_calibration_metrics.json",
    "probability_calibration_curve.png",
    "prediction_confidence_report.md",
    "operating_policy_thresholds.json",
    "company_prediction_results.csv",
    "company_risk_priority_queue.csv",
    "operating_policy_simulation.md",
]

EXPECTED_MODEL_STRATEGIES = {
    "logistic_regression_default",
    "logistic_regression_smote",
    "xgboost_default",
    "xgboost_default_tuned_threshold",
    "xgboost_smote",
    "xgboost_smote_tuned_threshold",
}

EXPECTED_ALERT_STRATEGIES = {
    "spc_only_torque_control_limit",
    "ml_selected_threshold",
    "ml_spc_combined",
}

EXPECTED_OPERATIONAL_POLICIES = {
    "no_alert_baseline",
    "spc_only",
    "xgboost_default",
    "xgboost_tuned_threshold",
    "ml_spc_combined",
}

EXPECTED_COST_SCENARIOS = {"conservative", "balanced", "high_downtime"}

EXPECTED_PRODUCT_SYSTEMS = {
    "IBM Maximo",
    "AWS IoT SiteWise",
    "Azure IoT Operations",
    "Siemens Insights Hub",
    "This system",
}

EXPECTED_WORKFLOW_METRICS = {
    "event_count",
    "draft_count",
    "decision_count",
    "event_to_draft_rate",
    "event_to_decision_rate",
    "draft_to_decision_rate",
    "operator_record_rate",
    "needs_review_retraining_candidates",
    "audit_log_count",
    "audit_failure_count",
}

EXPECTED_OPERATING_POLICIES_FOR_ENGINE = {"precision_first", "balanced", "recall_first"}

REQUIRED_PREDICTION_COLUMNS = [
    "UDI",
    "Product ID",
    "actual_machine_failure",
    "logistic_regression_prediction",
    "logistic_regression_probability",
    "xgboost_prediction",
    "xgboost_probability",
]


def pass_step(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str) -> None:
    raise AssertionError(message)


def require_file(path: Path) -> None:
    if not path.exists():
        fail(f"Missing required file: {path}")
    if path.is_file() and path.stat().st_size <= 0:
        fail(f"File is empty: {path}")


def verify_python_files_compile() -> None:
    python_files = sorted(SRC_DIR.glob("*.py")) + sorted(APP_DIR.glob("*.py"))
    if not python_files:
        fail("No Python files found in src/ or app/.")

    for path in python_files:
        py_compile.compile(str(path), doraise=True)

    pass_step(f"Python syntax compile passed for {len(python_files)} files.")


def verify_project_imports() -> None:
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    for module_name in [
        "data",
        "evaluate",
        "train_baseline",
        "stage4_explain",
        "predictive_spc",
        "future_deviation",
        "company_adapter",
        "operations_store",
        "realtime_ops",
        "api_server",
        "watch_realtime_folder",
        "compare_model_strategies",
        "compare_spc_ml_alerts",
        "mock_field_bridge",
        "verify_company_generalization",
        "verify_stage15_20",
        "verify_stage19_20_integration",
        "verify_stage19_20_design",
        "create_presentation_summary",
        "app.dashboard",
    ]:
        importlib.import_module(module_name)

    pass_step("Project module imports passed.")


def verify_dataset() -> pd.DataFrame:
    require_file(DATA_PATH)
    df = pd.read_csv(DATA_PATH)

    missing_columns = [column for column in REQUIRED_DATA_COLUMNS if column not in df.columns]
    if missing_columns:
        fail(f"Dataset is missing columns: {missing_columns}")

    target_values = set(df["Machine failure"].dropna().astype(int).unique().tolist())
    if not target_values.issubset({0, 1}):
        fail(f"Machine failure must be binary 0/1, found: {sorted(target_values)}")

    if len(df) <= 0:
        fail("Dataset has no rows.")

    pass_step(
        "Dataset check passed "
        f"({len(df)} rows, target counts {df['Machine failure'].value_counts().to_dict()})."
    )
    return df


def verify_output_files() -> None:
    for filename in REQUIRED_BASELINE_OUTPUTS + REQUIRED_EXTENDED_OUTPUTS:
        require_file(OUTPUT_DIR / filename)

    pass_step("Required baseline and presentation output files exist.")


def verify_metrics_json() -> dict:
    metrics_path = OUTPUT_DIR / "metrics.json"
    require_file(metrics_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    expected_dataset_path = DATA_PATH.resolve()
    actual_dataset_path = Path(metrics.get("dataset_path", "")).resolve()
    if actual_dataset_path != expected_dataset_path:
        fail(
            "metrics.json dataset_path is stale. "
            f"Expected {expected_dataset_path}, found {actual_dataset_path}."
        )

    for model_name in ["logistic_regression", "xgboost"]:
        model_metrics = metrics.get("models", {}).get(model_name)
        if model_metrics is None:
            fail(f"metrics.json is missing model metrics for {model_name}.")

        missing_keys = [key for key in REQUIRED_METRIC_KEYS if key not in model_metrics]
        if missing_keys:
            fail(f"{model_name} metrics are missing keys: {missing_keys}")

    best_model = max(
        metrics["models"],
        key=lambda name: metrics["models"][name]["pr_auc"],
    )
    if metrics.get("best_model_by_pr_auc") != best_model:
        fail(
            "best_model_by_pr_auc does not match the highest PR-AUC model. "
            f"Expected {best_model}, found {metrics.get('best_model_by_pr_auc')}."
        )

    pass_step(f"metrics.json check passed. Best model by PR-AUC: {best_model}.")
    return metrics


def verify_predictions_csv(metrics: dict) -> None:
    predictions_path = OUTPUT_DIR / "baseline_predictions.csv"
    require_file(predictions_path)
    predictions = pd.read_csv(predictions_path)

    missing_columns = [
        column for column in REQUIRED_PREDICTION_COLUMNS if column not in predictions.columns
    ]
    if missing_columns:
        fail(f"baseline_predictions.csv is missing columns: {missing_columns}")

    expected_rows = int(metrics.get("test_rows", 0))
    if len(predictions) != expected_rows:
        fail(
            "baseline_predictions.csv row count does not match metrics.json. "
            f"Expected {expected_rows}, found {len(predictions)}."
        )

    pass_step(f"baseline_predictions.csv check passed ({len(predictions)} rows).")


def verify_threshold_summary() -> None:
    threshold_path = OUTPUT_DIR / "threshold_summary.json"
    require_file(threshold_path)
    threshold_summary = json.loads(threshold_path.read_text(encoding="utf-8"))

    for key in ["selected_threshold", "selected_metrics", "default_0_5_metrics"]:
        if key not in threshold_summary:
            fail(f"threshold_summary.json is missing key: {key}")

    pass_step(
        "threshold_summary.json check passed "
        f"(selected threshold {threshold_summary['selected_threshold']})."
    )


def verify_spc_outputs(metrics: dict) -> None:
    spc_path = OUTPUT_DIR / "spc_timeseries.csv"
    summary_path = OUTPUT_DIR / "spc_summary.json"
    context_path = OUTPUT_DIR / "ai_report_context.json"

    require_file(spc_path)
    require_file(summary_path)
    require_file(context_path)

    spc = pd.read_csv(spc_path)
    required_columns = [
        "time_step",
        "simulated_timestamp",
        "UDI",
        "Product ID",
        "xgboost_probability",
        "selected_threshold",
        "risk_rolling_mean",
        "risk_ucl",
        "risk_lcl",
        "risk_status",
        "spc_risk_alert",
        "Torque [Nm]",
        "torque_ucl",
        "torque_lcl",
        "torque_beyond_control_limit",
    ]
    missing_columns = [column for column in required_columns if column not in spc.columns]
    if missing_columns:
        fail(f"spc_timeseries.csv is missing columns: {missing_columns}")

    expected_rows = int(metrics.get("test_rows", 0))
    if len(spc) != expected_rows:
        fail(
            "spc_timeseries.csv row count does not match metrics.json. "
            f"Expected {expected_rows}, found {len(spc)}."
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in [
        "selected_threshold",
        "rolling_window",
        "total_rows",
        "high_risk_count",
        "spc_risk_alert_count",
        "risk_ucl",
        "risk_lcl",
        "max_probability",
    ]:
        if key not in summary:
            fail(f"spc_summary.json is missing key: {key}")

    if int(summary["total_rows"]) != len(spc):
        fail("spc_summary.json total_rows does not match spc_timeseries.csv.")

    context = json.loads(context_path.read_text(encoding="utf-8"))
    for key in ["row", "sensor_values", "spc_summary", "top_shap_factors", "guardrail"]:
        if key not in context:
            fail(f"ai_report_context.json is missing key: {key}")

    mode = str(context.get("report_generation_mode", ""))
    allowed_report_prefixes = ("openai_responses_api:", "gemini_generate_content:")
    if not mode.startswith(allowed_report_prefixes):
        fail(
            "ai_report_context.json report_generation_mode must start with "
            "'openai_responses_api:' or 'gemini_generate_content:' for Stage 1~20 "
            f"GenAI verification, found: {mode}"
        )

    pass_step(
        "Predictive SPC outputs passed "
        f"({len(spc)} rows, {summary['high_risk_count']} high-risk rows)."
    )


def verify_future_deviation_outputs(metrics: dict) -> None:
    predictions_path = OUTPUT_DIR / "future_deviation_predictions.csv"
    metrics_path = OUTPUT_DIR / "future_deviation_metrics.json"
    chart_path = OUTPUT_DIR / "future_deviation_chart.png"
    summary_path = OUTPUT_DIR / "spc_summary.json"
    context_path = OUTPUT_DIR / "ai_report_context.json"

    require_file(predictions_path)
    require_file(metrics_path)
    require_file(chart_path)

    predictions = pd.read_csv(predictions_path)
    required_columns = [
        "time_step",
        "xgboost_probability",
        "future_max_risk_actual_h10",
        "future_deviation_actual_h10",
        "target_available",
        "predicted_future_max_risk_h10",
        "predicted_future_deviation_probability_h10",
        "predicted_future_deviation_h10",
        "future_horizon_steps",
    ]
    missing_columns = [column for column in required_columns if column not in predictions.columns]
    if missing_columns:
        fail(f"future_deviation_predictions.csv is missing columns: {missing_columns}")

    expected_rows = int(metrics.get("test_rows", 0))
    if len(predictions) != expected_rows:
        fail(
            "future_deviation_predictions.csv row count does not match metrics.json. "
            f"Expected {expected_rows}, found {len(predictions)}."
        )

    future_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    for key in ["horizon_steps", "train_rows", "validation_rows", "regression", "classification"]:
        if key not in future_metrics:
            fail(f"future_deviation_metrics.json is missing key: {key}")

    if int(future_metrics["horizon_steps"]) != 10:
        fail("future_deviation_metrics.json horizon_steps should be 10.")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if "future_deviation" not in summary:
        fail("spc_summary.json is missing future_deviation summary.")

    context = json.loads(context_path.read_text(encoding="utf-8"))
    if "future_prediction" not in context:
        fail("ai_report_context.json is missing future_prediction context.")

    pass_step(
        "Future deviation outputs passed "
        f"({len(predictions)} rows, horizon {future_metrics['horizon_steps']} steps)."
    )


def verify_stage14_company_outputs() -> None:
    custom_output_dir = OUTPUT_DIR / "custom_company_model"
    for filename in REQUIRED_STAGE14_OUTPUTS:
        require_file(custom_output_dir / filename)

    metrics = json.loads((custom_output_dir / "custom_metrics.json").read_text(encoding="utf-8"))
    if metrics.get("source") != "custom_company_csv":
        fail("custom_metrics.json source should be custom_company_csv.")
    if int(metrics.get("test_rows", 0)) <= 0:
        fail("custom_metrics.json test_rows should be greater than zero.")

    for model_name in ["logistic_regression", "xgboost"]:
        model_metrics = metrics.get("models", {}).get(model_name)
        if model_metrics is None:
            fail(f"custom_metrics.json is missing metrics for {model_name}.")
        missing_keys = [key for key in REQUIRED_METRIC_KEYS if key not in model_metrics]
        if missing_keys:
            fail(f"custom {model_name} metrics are missing keys: {missing_keys}")

    best_model = max(
        metrics["models"],
        key=lambda name: metrics["models"][name]["pr_auc"],
    )
    if metrics.get("best_model_by_pr_auc") != best_model:
        fail(
            "custom_metrics.json best_model_by_pr_auc does not match the highest PR-AUC model. "
            f"Expected {best_model}, found {metrics.get('best_model_by_pr_auc')}."
        )

    feature_schema = json.loads(
        (custom_output_dir / "feature_schema.json").read_text(encoding="utf-8")
    )
    if not feature_schema.get("encoded_feature_columns"):
        fail("feature_schema.json has no encoded feature columns.")

    threshold_summary = json.loads(
        (custom_output_dir / "custom_threshold_summary.json").read_text(encoding="utf-8")
    )
    for key in ["selected_threshold", "selected_metrics", "default_0_5_metrics"]:
        if key not in threshold_summary:
            fail(f"custom_threshold_summary.json is missing key: {key}")

    predictions = pd.read_csv(custom_output_dir / "custom_predictions.csv")
    if len(predictions) != int(metrics["test_rows"]):
        fail("custom_predictions.csv row count does not match custom_metrics.json.")
    for column in [
        "xgboost_probability",
        "xgboost_prediction_by_selected_threshold",
        "risk_status",
    ]:
        if column not in predictions.columns:
            fail(f"custom_predictions.csv is missing column: {column}")

    pass_step(
        "Stage 14 custom-company outputs passed "
        f"({len(predictions)} predictions, best model {best_model})."
    )


def verify_stage15_18_outputs() -> None:
    for filename in REQUIRED_STAGE15_18_OUTPUTS:
        require_file(OUTPUT_DIR / filename)

    architecture_text = (OUTPUT_DIR / "stage15_20_architecture.md").read_text(encoding="utf-8")
    for expected_text in ["Stage 15-lite", "Stage 16-lite", "Stage 17-lite", "Stage 18-lite"]:
        if expected_text not in architecture_text:
            fail(f"stage15_20_architecture.md is missing {expected_text}.")
    if "\ufffd" in architecture_text:
        fail("stage15_20_architecture.md contains a UTF-8 replacement character.")

    latest_events = pd.read_csv(OUTPUT_DIR / "realtime_stream/latest_events.csv")
    for column in ["event_id", "probability", "threshold", "risk_status"]:
        if column not in latest_events.columns:
            fail(f"latest_events.csv is missing column: {column}")
    if latest_events.empty:
        fail("latest_events.csv should contain at least one stream event.")

    db_path = OUTPUT_DIR / "operations.db"
    with sqlite3.connect(db_path) as connection:
        event_count = connection.execute("SELECT COUNT(*) FROM prediction_events").fetchone()[0]
        draft_count = connection.execute("SELECT COUNT(*) FROM work_order_drafts").fetchone()[0]
        decision_count = connection.execute("SELECT COUNT(*) FROM work_order_decisions").fetchone()[0]
    if event_count <= 0:
        fail("operations.db has no prediction_events rows.")
    if draft_count <= 0:
        fail("operations.db has no work_order_drafts rows.")
    if decision_count <= 0:
        fail("operations.db has no work_order_decisions rows.")

    draft_dir = OUTPUT_DIR / "work_order_drafts"
    if not draft_dir.exists():
        fail(f"Missing work-order draft directory: {draft_dir}")
    draft_files = sorted(draft_dir.glob("work_order_*.md"), key=lambda path: path.stat().st_mtime)
    if not draft_files:
        fail("No work-order Markdown drafts found.")
    latest_draft = draft_files[-1].read_text(encoding="utf-8")
    if "Stage 18-lite 작업지시 초안" not in latest_draft:
        fail("Latest work-order draft title is missing or corrupted.")
    if "\ufffd" in latest_draft:
        fail("Latest work-order draft contains a UTF-8 replacement character.")

    decisions = pd.read_csv(OUTPUT_DIR / "work_order_decisions.csv")
    for column in ["decision_id", "draft_id", "event_id", "operator_id", "decision", "note"]:
        if column not in decisions.columns:
            fail(f"work_order_decisions.csv is missing column: {column}")
    if decisions.empty:
        fail("work_order_decisions.csv should contain at least one operator decision.")
    allowed_decisions = {"approve", "reject", "needs_review"}
    if not set(decisions["decision"].astype(str)).issubset(allowed_decisions):
        fail("work_order_decisions.csv contains an unsupported decision value.")

    pass_step(
        "Stage 15~18 local operations outputs passed "
        f"({event_count} events, {draft_count} drafts, {decision_count} decisions)."
    )


def verify_comparison_outputs() -> None:
    for filename in REQUIRED_COMPARISON_OUTPUTS:
        require_file(OUTPUT_DIR / filename)

    model_comparison = pd.read_csv(OUTPUT_DIR / "model_strategy_comparison.csv")
    required_model_columns = [
        "strategy_id",
        "display_name",
        "uses_smote",
        "threshold_strategy",
        "threshold",
        "precision",
        "recall",
        "f1_score",
        "roc_auc",
        "pr_auc",
        "alert_count",
        "false_positive",
        "false_negative",
    ]
    missing_model_columns = [
        column for column in required_model_columns if column not in model_comparison.columns
    ]
    if missing_model_columns:
        fail(f"model_strategy_comparison.csv is missing columns: {missing_model_columns}")

    actual_model_strategies = set(model_comparison["strategy_id"].astype(str))
    missing_model_strategies = EXPECTED_MODEL_STRATEGIES - actual_model_strategies
    if missing_model_strategies:
        fail(f"model_strategy_comparison.csv is missing strategies: {sorted(missing_model_strategies)}")

    if model_comparison["pr_auc"].isna().any() or model_comparison["f1_score"].isna().any():
        fail("model_strategy_comparison.csv contains missing PR-AUC or F1 values.")

    model_summary = (OUTPUT_DIR / "model_strategy_summary.md").read_text(encoding="utf-8")
    if "does not prove real factory cost reduction" not in model_summary:
        fail("model_strategy_summary.md is missing the cost-reduction guardrail.")

    spc_comparison = pd.read_csv(OUTPUT_DIR / "spc_vs_ml_comparison.csv")
    required_alert_columns = [
        "strategy_id",
        "display_name",
        "precision",
        "recall",
        "f1_score",
        "alert_count",
        "false_positive",
        "false_negative",
        "actual_failure_count",
        "total_rows",
    ]
    missing_alert_columns = [
        column for column in required_alert_columns if column not in spc_comparison.columns
    ]
    if missing_alert_columns:
        fail(f"spc_vs_ml_comparison.csv is missing columns: {missing_alert_columns}")

    actual_alert_strategies = set(spc_comparison["strategy_id"].astype(str))
    missing_alert_strategies = EXPECTED_ALERT_STRATEGIES - actual_alert_strategies
    if missing_alert_strategies:
        fail(f"spc_vs_ml_comparison.csv is missing strategies: {sorted(missing_alert_strategies)}")

    spc_summary = (OUTPUT_DIR / "spc_vs_ml_summary.md").read_text(encoding="utf-8")
    if "does not prove real maintenance cost reduction" not in spc_summary:
        fail("spc_vs_ml_summary.md is missing the maintenance-cost guardrail.")

    mock_summary = json.loads((OUTPUT_DIR / "mock_field_bridge_summary.json").read_text(encoding="utf-8"))
    if "local mock bridge only" not in str(mock_summary.get("scope", "")):
        fail("mock_field_bridge_summary.json is missing the local-mock scope.")
    if mock_summary.get("protocol") not in {"mqtt_mock", "opcua_mock"}:
        fail("mock_field_bridge_summary.json has an unsupported protocol.")
    if int(mock_summary.get("event_count", 0)) <= 0:
        fail("mock_field_bridge_summary.json should contain at least one event.")

    operational = pd.read_csv(OUTPUT_DIR / "operational_value_simulation.csv")
    required_operational_columns = [
        "scenario_id",
        "policy_id",
        "precision",
        "recall",
        "f1_score",
        "alert_count",
        "false_alarm_count",
        "missed_failure_count",
        "operating_cost_units",
        "normalized_operating_cost",
    ]
    missing_operational_columns = [
        column for column in required_operational_columns if column not in operational.columns
    ]
    if missing_operational_columns:
        fail(f"operational_value_simulation.csv is missing columns: {missing_operational_columns}")
    if EXPECTED_OPERATIONAL_POLICIES - set(operational["policy_id"].astype(str)):
        fail("operational_value_simulation.csv is missing one or more required alert policies.")
    if EXPECTED_COST_SCENARIOS - set(operational["scenario_id"].astype(str)):
        fail("operational_value_simulation.csv is missing one or more cost scenarios.")
    if operational["normalized_operating_cost"].isna().any():
        fail("operational_value_simulation.csv contains missing normalized costs.")
    operational_summary = (OUTPUT_DIR / "operational_value_simulation.md").read_text(encoding="utf-8")
    if "not a real factory cost-reduction proof" not in operational_summary:
        fail("operational_value_simulation.md is missing the factory-cost guardrail.")

    product_comparison = pd.read_csv(OUTPUT_DIR / "product_capability_comparison.csv")
    required_product_columns = [
        "system",
        "sensor_input",
        "model_reproducibility",
        "spc_integration",
        "explainability",
        "work_order_workflow",
        "deployment_level",
        "research_reproducibility",
    ]
    missing_product_columns = [
        column for column in required_product_columns if column not in product_comparison.columns
    ]
    if missing_product_columns:
        fail(f"product_capability_comparison.csv is missing columns: {missing_product_columns}")
    if EXPECTED_PRODUCT_SYSTEMS - set(product_comparison["system"].astype(str)):
        fail("product_capability_comparison.csv is missing one or more commercial reference systems.")
    product_summary = (OUTPUT_DIR / "product_capability_comparison.md").read_text(encoding="utf-8")
    if "not a claim that this system outperforms commercial SaaS products" not in product_summary:
        fail("product_capability_comparison.md is missing the commercial-product guardrail.")

    workflow_summary = pd.read_csv(OUTPUT_DIR / "workflow_traceability_summary.csv")
    if EXPECTED_WORKFLOW_METRICS - set(workflow_summary["metric"].astype(str)):
        fail("workflow_traceability_summary.csv is missing one or more required traceability metrics.")
    workflow_markdown = (OUTPUT_DIR / "workflow_traceability_summary.md").read_text(encoding="utf-8")
    if "not automatic maintenance-command execution" not in workflow_markdown:
        fail("workflow_traceability_summary.md is missing the automatic-maintenance guardrail.")

    evidence_pack = (OUTPUT_DIR / "thesis_evidence_pack.md").read_text(encoding="utf-8")
    required_evidence_phrases = [
        "Do Not Claim",
        "85% detection-time reduction",
        "30% cost reduction",
        "validated factory ROI",
        "Commercial Reference Systems",
    ]
    missing_evidence_phrases = [
        phrase for phrase in required_evidence_phrases if phrase not in evidence_pack
    ]
    if missing_evidence_phrases:
        fail(f"thesis_evidence_pack.md is missing guardrail phrases: {missing_evidence_phrases}")

    pass_step(
        "Comparison and mock-bridge outputs passed "
        f"({len(model_comparison)} model rows, {len(spc_comparison)} alert rows, "
        f"{len(operational)} operating-value rows)."
    )


def verify_stage19_20_design_outputs() -> None:
    from verify_stage19_20_design import verify_stage19_20_design

    verify_stage19_20_design(OUTPUT_DIR / "stage19_20_operations_design.md")


def verify_smart_preprocessing_prediction_outputs() -> None:
    quality = pd.read_csv(OUTPUT_DIR / "company_input_quality_report.csv")
    required_quality_columns = [
        "canonical_column",
        "source_column",
        "issue",
        "severity",
        "affected_rows",
        "detail",
    ]
    missing_quality_columns = [
        column for column in required_quality_columns if column not in quality.columns
    ]
    if missing_quality_columns:
        fail(f"company_input_quality_report.csv is missing columns: {missing_quality_columns}")

    predictions = pd.read_csv(OUTPUT_DIR / "company_prediction_results.csv")
    required_prediction_columns = [
        "raw_probability",
        "calibrated_probability",
        "risk_status",
        "risk_priority_score",
        "recommendation",
    ]
    missing_prediction_columns = [
        column for column in required_prediction_columns if column not in predictions.columns
    ]
    if missing_prediction_columns:
        fail(f"company_prediction_results.csv is missing columns: {missing_prediction_columns}")
    if predictions["calibrated_probability"].isna().any():
        fail("company_prediction_results.csv contains missing calibrated probabilities.")

    priority = pd.read_csv(OUTPUT_DIR / "company_risk_priority_queue.csv")
    if "priority_rank" not in priority.columns or "risk_priority_score" not in priority.columns:
        fail("company_risk_priority_queue.csv is missing priority columns.")
    if len(priority) != len(predictions):
        fail("company_risk_priority_queue.csv row count should match prediction results.")

    calibration = json.loads((OUTPUT_DIR / "probability_calibration_metrics.json").read_text(encoding="utf-8"))
    if calibration.get("selected_method") not in {"raw", "sigmoid", "isotonic"}:
        fail("probability_calibration_metrics.json has an invalid selected_method.")
    if "brier_scores" not in calibration:
        fail("probability_calibration_metrics.json is missing brier_scores.")

    policy = json.loads((OUTPUT_DIR / "operating_policy_thresholds.json").read_text(encoding="utf-8"))
    missing_policies = EXPECTED_OPERATING_POLICIES_FOR_ENGINE - set(policy.get("policies", {}).keys())
    if missing_policies:
        fail(f"operating_policy_thresholds.json is missing policies: {sorted(missing_policies)}")

    report_text = (
        (OUTPUT_DIR / "company_preprocessing_report.md").read_text(encoding="utf-8")
        + (OUTPUT_DIR / "prediction_confidence_report.md").read_text(encoding="utf-8")
        + (OUTPUT_DIR / "operating_policy_simulation.md").read_text(encoding="utf-8")
    )
    required_phrases = [
        "does not prove real company-data model performance",
        "not a field-certified reliability score",
        "not factory-approved operating policies",
    ]
    missing_phrases = [phrase for phrase in required_phrases if phrase not in report_text]
    if missing_phrases:
        fail(f"Smart preprocessing reports are missing guardrail phrases: {missing_phrases}")

    pass_step(
        "Smart preprocessing/prediction outputs passed "
        f"({len(predictions)} prediction rows, calibration {calibration['selected_method']})."
    )


def verify_utf8_documents() -> None:
    documents = [
        PROJECT_ROOT / "README.md",
        OUTPUT_DIR / "presentation_summary.md",
        OUTPUT_DIR / "research_plan_may11.md",
        OUTPUT_DIR / "midterm_presentation_guide.md",
        OUTPUT_DIR / "midterm_qna_may11.md",
        OUTPUT_DIR / "stage10_operations_summary.md",
        OUTPUT_DIR / "ai_manager_report.md",
        OUTPUT_DIR / "final_paper_outline.md",
        OUTPUT_DIR / "final_presentation_plan.md",
        OUTPUT_DIR / "stage15_20_architecture.md",
        OUTPUT_DIR / "stage19_20_operations_design.md",
        OUTPUT_DIR / "model_strategy_summary.md",
        OUTPUT_DIR / "spc_vs_ml_summary.md",
        OUTPUT_DIR / "mock_field_bridge_summary.md",
        OUTPUT_DIR / "operational_value_simulation.md",
        OUTPUT_DIR / "product_capability_comparison.md",
        OUTPUT_DIR / "workflow_traceability_summary.md",
        OUTPUT_DIR / "thesis_evidence_pack.md",
        OUTPUT_DIR / "company_preprocessing_report.md",
        OUTPUT_DIR / "prediction_confidence_report.md",
        OUTPUT_DIR / "operating_policy_simulation.md",
    ]

    for path in documents:
        require_file(path)
        text = path.read_text(encoding="utf-8")
        if "\ufffd" in text:
            fail(f"Replacement character found in UTF-8 document: {path}")

    pass_step("UTF-8 document checks passed.")


def main() -> None:
    print(f"Verifying project at: {PROJECT_ROOT}")
    verify_python_files_compile()
    verify_project_imports()
    verify_dataset()
    verify_output_files()
    metrics = verify_metrics_json()
    verify_predictions_csv(metrics)
    verify_threshold_summary()
    verify_spc_outputs(metrics)
    verify_future_deviation_outputs(metrics)
    verify_stage14_company_outputs()
    verify_stage15_18_outputs()
    verify_comparison_outputs()
    verify_smart_preprocessing_prediction_outputs()
    verify_stage19_20_design_outputs()
    verify_utf8_documents()
    print("All project verification checks passed.")


if __name__ == "__main__":
    main()
