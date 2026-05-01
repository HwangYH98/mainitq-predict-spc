import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SRC_DIR = PROJECT_ROOT / "src"
COMPANY_OUTPUT_DIR = OUTPUT_DIR / "custom_company_model"
OPERATIONS_DB_PATH = OUTPUT_DIR / "operations.db"
STAGE15_20_ARCHITECTURE_PATH = OUTPUT_DIR / "stage15_20_architecture.md"
WORK_ORDER_DECISIONS_PATH = OUTPUT_DIR / "work_order_decisions.csv"

if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from company_adapter import (
    UNIT_PRESETS,
    save_custom_training_outputs,
    train_custom_company_model,
)
from data import ID_COLUMNS, preprocess_features, prepare_train_test_data
from operations_store import (
    list_prediction_events,
    list_work_order_decisions,
    list_work_order_drafts,
)
from predictive_spc import genai_ai_report
from train_baseline import RANDOM_STATE, TEST_SIZE, build_models

REQUIRED_FILES = {
    "metrics": OUTPUT_DIR / "metrics.json",
    "threshold": OUTPUT_DIR / "threshold_summary.json",
    "presentation": OUTPUT_DIR / "presentation_summary.md",
    "research_plan": OUTPUT_DIR / "research_plan_may11.md",
    "midterm_guide": OUTPUT_DIR / "midterm_presentation_guide.md",
    "midterm_qna": OUTPUT_DIR / "midterm_qna_may11.md",
    "rehearsal_checklist": OUTPUT_DIR / "rehearsal_checklist_may11.md",
    "backup_checklist": OUTPUT_DIR / "presentation_day_backup_checklist.md",
    "final_roadmap": OUTPUT_DIR / "final_stage_roadmap.md",
    "stage9_applicability": OUTPUT_DIR / "stage9_field_applicability.md",
    "stage10_operations": OUTPUT_DIR / "stage10_operations_summary.md",
    "stage19_20_design": OUTPUT_DIR / "stage19_20_operations_design.md",
    "spc_timeseries": OUTPUT_DIR / "spc_timeseries.csv",
    "spc_summary": OUTPUT_DIR / "spc_summary.json",
    "spc_risk_chart": OUTPUT_DIR / "spc_risk_chart.png",
    "spc_control_chart": OUTPUT_DIR / "spc_control_chart.png",
    "future_predictions": OUTPUT_DIR / "future_deviation_predictions.csv",
    "future_metrics": OUTPUT_DIR / "future_deviation_metrics.json",
    "future_chart": OUTPUT_DIR / "future_deviation_chart.png",
    "ai_report_context": OUTPUT_DIR / "ai_report_context.json",
    "ai_manager_report": OUTPUT_DIR / "ai_manager_report.md",
    "confusion_matrix": OUTPUT_DIR / "confusion_matrix.png",
    "pr_curve": OUTPUT_DIR / "pr_curve.png",
    "threshold_tuning": OUTPUT_DIR / "threshold_tuning.png",
    "shap_summary": OUTPUT_DIR / "shap_summary.png",
    "shap_bar": OUTPUT_DIR / "shap_bar.png",
    "local_case": OUTPUT_DIR / "local_case_explanation.md",
    "predictions": OUTPUT_DIR / "baseline_predictions.csv",
}

RAW_UPLOAD_COLUMNS = [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]

FEATURE_LABELS = {
    "air_temperature_k": "Air temperature [K]",
    "process_temperature_k": "Process temperature [K]",
    "rotational_speed_rpm": "Rotational speed [rpm]",
    "torque_nm": "Torque [Nm]",
    "tool_wear_min": "Tool wear [min]",
    "type_h": "Type=H",
    "type_l": "Type=L",
    "type_m": "Type=M",
}

FEATURE_GUIDANCE = {
    "air_temperature_k": "주변 온도와 냉각 조건을 확인합니다.",
    "process_temperature_k": "공정 온도 설정값과 냉각 상태를 점검합니다.",
    "rotational_speed_rpm": "회전 속도 변동, 모터 부하, 구동부 상태를 확인합니다.",
    "torque_nm": "토크 상승 원인을 확인하고 베어링, 축 정렬, 부하 상태를 점검합니다.",
    "tool_wear_min": "공구 마모 시간과 교체 주기를 확인합니다.",
    "type_h": "제품 Type H 조건에서만 반복되는 위험 패턴이 있는지 확인합니다.",
    "type_l": "제품 Type L 조건에서만 반복되는 위험 패턴이 있는지 확인합니다.",
    "type_m": "제품 Type M 조건에서만 반복되는 위험 패턴이 있는지 확인합니다.",
}


def configure_page() -> None:
    """Set page metadata and presentation-friendly styling."""
    st.set_page_config(
        page_title="Predictive SPC Stage 1~20 Local PoC",
        page_icon="chart_with_upwards_trend",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        :root {
            --ink: #17202a;
            --muted: #637381;
            --line: #d8dee9;
            --signal: #0f766e;
            --warning: #c97700;
            --soft: #fff7e6;
            --danger: #b42318;
            --safe: #0f766e;
        }
        .main {
            background: linear-gradient(135deg, #f6f8f5 0%, #eef5f3 45%, #fff8ed 100%);
        }
        .block-container {
            padding-top: 2rem;
        }
        .hero {
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 28px 30px;
            background:
                radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 32%),
                linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 247, 0.88));
            box-shadow: 0 18px 45px rgba(23, 32, 42, 0.08);
            margin-bottom: 1rem;
        }
        .hero h1 {
            color: var(--ink);
            font-size: 2.25rem;
            margin-bottom: 0.35rem;
            letter-spacing: -0.04em;
        }
        .hero p {
            color: var(--muted);
            font-size: 1.05rem;
            margin: 0;
        }
        .stage-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.35rem 0.75rem;
            background: #e6f4f1;
            color: #0f5f59;
            font-weight: 700;
            margin-bottom: 0.8rem;
        }
        .metric-card {
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 18px;
            background: rgba(255,255,255,0.9);
            min-height: 118px;
        }
        .metric-card .label {
            color: var(--muted);
            font-size: 0.92rem;
            margin-bottom: 0.25rem;
        }
        .metric-card .value {
            color: var(--ink);
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
        }
        .metric-card .note {
            color: var(--signal);
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }
        .callout {
            border-left: 5px solid var(--warning);
            background: var(--soft);
            padding: 1rem 1.2rem;
            border-radius: 14px;
            color: var(--ink);
        }
        .risk-high {
            border: 1px solid rgba(180, 35, 24, 0.25);
            color: var(--danger);
            background: #fff1f0;
            border-radius: 16px;
            padding: 1rem;
            font-weight: 800;
            text-align: center;
        }
        .risk-normal {
            border: 1px solid rgba(15, 118, 110, 0.25);
            color: var(--safe);
            background: #eefaf7;
            border-radius: 16px;
            padding: 1rem;
            font-weight: 800;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_missing_files(missing_files: list[Path]) -> None:
    """Show beginner-friendly recovery commands when outputs are missing."""
    st.error("필요한 outputs 파일이 아직 생성되지 않았습니다.")
    st.write("아래 파일을 찾지 못했습니다.")
    for path in missing_files:
        st.code(str(path), language="text")

    st.markdown("먼저 아래 중 하나를 실행하세요.")
    st.code("run_all.bat", language="powershell")
    st.code(
        ".\\.venv\\Scripts\\python.exe src\\train_baseline.py\n"
        ".\\.venv\\Scripts\\python.exe src\\stage4_explain.py\n"
        ".\\.venv\\Scripts\\python.exe src\\predictive_spc.py\n"
        ".\\.venv\\Scripts\\python.exe src\\future_deviation.py\n"
        ".\\.venv\\Scripts\\python.exe src\\create_presentation_summary.py",
        language="powershell",
    )


@st.cache_data
def load_json(path: Path) -> dict:
    """Load a JSON file from outputs."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@st.cache_data
def load_markdown(path: Path) -> str:
    """Load a Markdown file from outputs."""
    return path.read_text(encoding="utf-8")


@st.cache_data
def load_predictions(path: Path) -> pd.DataFrame:
    """Load saved test-set predictions for the row simulation tab."""
    return pd.read_csv(path)


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    """Load a saved CSV artifact."""
    return pd.read_csv(path)


@st.cache_resource
def train_stage7_inference_bundle() -> tuple[object, list[str], object]:
    """
    Train the same XGBoost baseline for uploaded CSV inference.

    This keeps Stage 7-lite self-contained for presentation. It does not create
    a production model registry or real-time data connection yet.
    """
    import shap

    X_train, _, y_train, _, _ = prepare_train_test_data(
        csv_path=DATA_PATH,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )
    model = build_models(y_train)["xgboost"]
    model.fit(X_train, y_train)
    explainer = shap.TreeExplainer(model)
    return model, list(X_train.columns), explainer


def uploaded_predictions_dataframe(
    uploaded_df: pd.DataFrame,
    probabilities,
    selected_threshold: float,
) -> pd.DataFrame:
    """Attach failure probabilities and risk labels to uploaded rows."""
    result_df = uploaded_df.copy()
    result_df.insert(0, "input_row", range(len(result_df)))
    result_df["xgboost_failure_probability"] = probabilities
    result_df["selected_threshold"] = selected_threshold
    result_df["risk_status"] = [
        "High Risk" if probability >= selected_threshold else "Normal"
        for probability in probabilities
    ]
    return result_df


def calculate_uploaded_shap_values(explainer, features: pd.DataFrame) -> pd.DataFrame:
    """Calculate SHAP values for rows uploaded in the Stage 7-lite tab."""
    shap_values = explainer.shap_values(features)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    return pd.DataFrame(shap_values, columns=features.columns, index=features.index)


def top_failure_factors(
    features: pd.DataFrame,
    shap_values: pd.DataFrame,
    selected_position: int,
) -> pd.DataFrame:
    """Find the strongest positive factors pushing one uploaded row toward failure."""
    row_values = features.iloc[selected_position]
    row_shap = shap_values.iloc[selected_position]
    positive_shap = row_shap[row_shap > 0].sort_values(ascending=False)

    if positive_shap.empty:
        positive_shap = row_shap.abs().sort_values(ascending=False)

    rows = []
    for feature, shap_value in positive_shap.head(3).items():
        rows.append(
            {
                "Feature": FEATURE_LABELS.get(feature, feature),
                "Feature value": row_values[feature],
                "SHAP value": round(float(shap_value), 4),
                "Suggested check": FEATURE_GUIDANCE.get(feature, "관련 센서와 설비 상태를 현장 기준으로 확인합니다."),
            }
        )
    return pd.DataFrame(rows)


def prescription_draft(
    selected_row: pd.Series,
    factors: pd.DataFrame,
    selected_threshold: float,
) -> str:
    """Build a simple manager-facing maintenance note without calling an LLM."""
    probability = float(selected_row["xgboost_failure_probability"])
    status = selected_row["risk_status"]

    if factors.empty:
        factor_text = "주요 양의 SHAP 요인을 찾지 못했습니다."
    else:
        factor_text = ", ".join(factors["Feature"].astype(str).head(3).tolist())

    if status == "High Risk":
        action = (
            "관리자 참고용 권고: 해당 row는 threshold를 넘었으므로 설비 부하, 회전 조건, "
            "공구 마모 상태를 우선 점검하고 실제 작업 이력과 함께 확인합니다."
        )
    else:
        action = (
            "관리자 참고용 권고: 현재 row는 threshold 아래이므로 즉시 경고 대상은 아니지만, "
            "반복적으로 확률이 상승하는지 추세를 확인합니다."
        )

    return (
        f"- Risk status: `{status}`\n"
        f"- Failure probability: `{probability:.4f}` / threshold `{selected_threshold:.2f}`\n"
        f"- Main evidence: {factor_text}\n"
        f"- {action}\n\n"
        "주의: 이 문장은 실제 LLM 호출이 아니라 SHAP 근거를 사용한 Stage 8-lite 처방 초안입니다. "
        "최종 정비 지시는 현장 담당자가 확정해야 합니다."
    )


def future_prediction_context(future_predictions: pd.DataFrame, time_step: int) -> dict:
    """Return the future-deviation prediction for one simulated stream row."""
    matched = future_predictions[future_predictions["time_step"] == time_step]
    if matched.empty:
        return {}

    row = matched.iloc[0]
    actual_value = row.get("future_deviation_actual_h10")
    return {
        "horizon_steps": int(row.get("future_horizon_steps", 10)),
        "predicted_future_max_risk_h10": round(
            float(row["predicted_future_max_risk_h10"]),
            6,
        ),
        "predicted_future_deviation_probability_h10": round(
            float(row["predicted_future_deviation_probability_h10"]),
            6,
        ),
        "predicted_future_deviation_h10": bool(row["predicted_future_deviation_h10"]),
        "actual_future_deviation_h10": None
        if pd.isna(actual_value)
        else bool(int(actual_value)),
        "target_available": bool(row.get("target_available", False)),
    }


def realtime_prescription_note(
    current_probability: float,
    selected_threshold: float,
    future_context: dict,
    factors: pd.DataFrame,
) -> str:
    """Build the worker-facing note for the real-time PoC tab."""
    if factors.empty:
        factor_text = "확인된 SHAP 상위 요인이 없습니다."
    else:
        factor_text = ", ".join(factors["Feature"].astype(str).head(3).tolist())

    current_high = current_probability >= selected_threshold
    future_high = bool(future_context.get("predicted_future_deviation_h10", False))
    future_risk = float(future_context.get("predicted_future_max_risk_h10", 0.0))
    future_probability = float(
        future_context.get("predicted_future_deviation_probability_h10", 0.0)
    )

    if current_high and future_high:
        action = (
            "현재 row와 미래 10-step 예측이 모두 위험 신호입니다. 토크, 회전 속도, 공구 마모를 "
            "우선 점검하고 다음 10 step 구간을 집중 모니터링합니다."
        )
    elif current_high:
        action = (
            "현재 row가 threshold를 넘었습니다. 즉시 경고 후보로 표시하되, 실제 정비 여부는 "
            "현장 설비 상태와 작업 이력을 함께 확인한 뒤 결정합니다."
        )
    elif future_high:
        action = (
            "현재 row는 threshold 아래지만 미래 10-step 이탈 후보입니다. 다음 구간에서 같은 "
            "센서 패턴이 반복되는지 확인하고 예방 점검 후보로 기록합니다."
        )
    else:
        action = (
            "현재와 미래 10-step 모두 즉시 경고 수준은 아닙니다. 다만 risk trend가 계속 "
            "상승하는지 대시보드에서 추적합니다."
        )

    return "\n".join(
        [
            "### 작업자 참고 권고",
            "",
            f"- 현재 고장 확률: `{current_probability:.4f}` / threshold `{selected_threshold:.2f}`",
            f"- 미래 10-step 최대 risk 예측: `{future_risk:.4f}`",
            f"- 미래 이탈 확률: `{future_probability:.4f}`",
            f"- 주요 SHAP 근거: {factor_text}",
            f"- 권고: {action}",
            "",
            "주의: 이 문장은 자동 정비 명령이 아니라 발표용 PoC의 작업자/관리자 참고 권고입니다.",
        ]
    )


def realtime_report_context(
    selected_row: pd.Series,
    current_probability: float,
    selected_threshold: float,
    future_context: dict,
    spc_summary: dict,
    factors: pd.DataFrame,
) -> dict:
    """Build a row-specific LLM/fallback context for the real-time PoC tab."""
    shap_factors = []
    for item in factors.to_dict(orient="records"):
        shap_factors.append(
            {
                "feature": item["Feature"],
                "feature_value": item["Feature value"],
                "shap_value": item["SHAP value"],
                "suggested_check": item["Suggested check"],
            }
        )

    return {
        "report_scope": "simulated real-time worker reference report",
        "generated_at": "created from Streamlit real-time PoC tab",
        "simulation_note": (
            "AI4I rows are replayed by UDI order as a simulated stream. "
            "This is not a live factory sensor feed."
        ),
        "row": {
            "time_step": int(selected_row["time_step"]),
            "simulated_timestamp": str(selected_row["simulated_timestamp"]),
            "UDI": int(selected_row["UDI"]),
            "Product ID": str(selected_row["Product ID"]),
            "actual_machine_failure": int(selected_row["actual_machine_failure"]),
            "xgboost_probability": round(float(current_probability), 6),
            "selected_threshold": round(float(selected_threshold), 6),
            "risk_status": "High Risk" if current_probability >= selected_threshold else "Normal",
            "risk_beyond_control_limit": bool(selected_row["risk_beyond_control_limit"]),
            "torque_beyond_control_limit": bool(selected_row["torque_beyond_control_limit"]),
        },
        "sensor_values": {
            "Type": str(selected_row["Type"]),
            "Air temperature [K]": round(float(selected_row["Air temperature [K]"]), 4),
            "Process temperature [K]": round(float(selected_row["Process temperature [K]"]), 4),
            "Rotational speed [rpm]": round(float(selected_row["Rotational speed [rpm]"]), 4),
            "Torque [Nm]": round(float(selected_row["Torque [Nm]"]), 4),
            "Tool wear [min]": round(float(selected_row["Tool wear [min]"]), 4),
        },
        "future_prediction": future_context,
        "spc_summary": spc_summary,
        "top_shap_factors": shap_factors,
        "guardrail": (
            "Use current risk, future 10-step deviation prediction, and SHAP evidence "
            "only as a worker or manager reference. Do not write an automatic maintenance order."
        ),
    }


def model_metrics_dataframe(metrics: dict) -> pd.DataFrame:
    """Convert model metrics JSON into a presentation-friendly table."""
    labels = {
        "logistic_regression": "Logistic Regression",
        "xgboost": "XGBoost",
    }
    rows = []

    for model_key, model_metrics in metrics["models"].items():
        rows.append(
            {
                "Model": labels.get(model_key, model_key),
                "Precision": model_metrics["precision"],
                "Recall": model_metrics["recall"],
                "F1-score": model_metrics["f1_score"],
                "ROC-AUC": model_metrics["roc_auc"],
                "PR-AUC": model_metrics["pr_auc"],
            }
        )

    return pd.DataFrame(rows)


def threshold_dataframe(threshold_summary: dict) -> pd.DataFrame:
    """Convert threshold summary JSON into a comparison table."""
    selected_threshold = threshold_summary["selected_threshold"]
    return pd.DataFrame(
        [
            {
                "Threshold": "0.50 (default)",
                "Precision": threshold_summary["default_0_5_metrics"]["precision"],
                "Recall": threshold_summary["default_0_5_metrics"]["recall"],
                "F1-score": threshold_summary["default_0_5_metrics"]["f1_score"],
            },
            {
                "Threshold": f"{selected_threshold:.2f} (selected by F1)",
                "Precision": threshold_summary["selected_metrics"]["precision"],
                "Recall": threshold_summary["selected_metrics"]["recall"],
                "F1-score": threshold_summary["selected_metrics"]["f1_score"],
            },
        ]
    )


def metric_card(label: str, value: str, note: str) -> None:
    """Render a compact metric card."""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Render dashboard title and stage badge."""
    st.markdown(
        """
        <div class="hero">
            <div class="stage-badge">Stage 1~20 local integration PoC · Streamlit dashboard</div>
            <h1>Predictive SPC Capstone Results Dashboard</h1>
            <p>AI4I 2020 row playback, Predictive SPC, Gemini/OpenAI GenAI 관리자 리포트, field-event API, SQLite 이력, human decision logging을 한 화면에서 확인하는 로컬 통합 PoC입니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_tab(metrics: dict, threshold_summary: dict) -> None:
    """Render the high-level performance summary."""
    xgboost = metrics["models"]["xgboost"]
    selected = threshold_summary["selected_metrics"]
    selected_threshold = float(threshold_summary["selected_threshold"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Best Model", "XGBoost", "PR-AUC 기준 대표 모델")
    with col2:
        metric_card("XGBoost PR-AUC", f"{xgboost['pr_auc']:.4f}", "불균형 데이터에서 중요")
    with col3:
        metric_card("Selected Threshold", f"{threshold_summary['selected_threshold']:.2f}", "F1-score 기준 선택")
    with col4:
        metric_card("Tuned F1-score", f"{selected['f1_score']:.4f}", "0.50 대비 개선")

    st.markdown(
        f"""
        <div class="callout">
        <strong>발표 핵심 메시지:</strong>
        Logistic Regression보다 XGBoost가 PR-AUC 기준으로 우수했고,
        threshold를 {selected_threshold:.2f}로 조정하면 F1-score가 {selected['f1_score']:.4f}까지 개선됩니다.
        SHAP 해석은 torque, rotational speed, tool wear 같은 센서 변수가 고장 예측에 어떻게 기여했는지 보여줍니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("5월 11일 시연 흐름")
    st.markdown(
        """
        1. Baseline 모델 비교 결과를 보여줍니다.
        2. Threshold 조정으로 의사결정 기준을 개선한 점을 설명합니다.
        3. SHAP 그림과 개별 사례로 “왜 고장이라고 예측했는지”를 설명합니다.
        4. Row 시뮬레이션으로 test row별 고장 확률 변화를 보여줍니다.
        5. 중간발표 진행안 탭으로 PPT 없이 말할 순서를 확인합니다.
        6. 현장 CSV MVP와 Stage 9 실제 적용성 탭으로 실사업장 확장 방향을 설명합니다.
        7. Stage 10 운영 요약 탭에서 최종 통합 MVP와 다운로드 산출물을 보여줍니다.
        """
    )


def render_model_tab(metrics: dict) -> None:
    """Render model comparison table and figures."""
    st.subheader("Baseline 모델 비교")
    st.dataframe(model_metrics_dataframe(metrics), width="stretch", hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.image(str(REQUIRED_FILES["confusion_matrix"]), caption="Confusion Matrix Comparison", width="stretch")
    with col2:
        st.image(str(REQUIRED_FILES["pr_curve"]), caption="Precision-Recall Curve Comparison", width="stretch")


def render_threshold_tab(threshold_summary: dict) -> None:
    """Render threshold tuning results."""
    selected_threshold = float(threshold_summary["selected_threshold"])

    st.subheader("Threshold 조정 결과")
    st.dataframe(threshold_dataframe(threshold_summary), width="stretch", hide_index=True)

    st.image(
        str(REQUIRED_FILES["threshold_tuning"]),
        caption="Threshold별 Precision / Recall / F1-score 변화",
        width="stretch",
    )

    st.info(
        "기본 threshold 0.50은 recall이 높지만 precision이 낮습니다. "
        f"F1 기준으로 {selected_threshold:.2f}을 선택하면 precision과 F1-score가 좋아져 발표용 의사결정 기준으로 설명하기 쉽습니다."
    )


def render_shap_tab() -> None:
    """Render global SHAP plots."""
    st.subheader("SHAP 해석")
    col1, col2 = st.columns(2)
    with col1:
        st.image(str(REQUIRED_FILES["shap_summary"]), caption="SHAP Summary Plot", width="stretch")
    with col2:
        st.image(str(REQUIRED_FILES["shap_bar"]), caption="Mean Absolute SHAP Importance", width="stretch")

    st.markdown(
        "SHAP은 XGBoost가 어떤 센서 변수를 근거로 고장 확률을 높이거나 낮췄는지 보여주는 해석 레이어입니다."
    )


def render_row_simulation_tab(predictions: pd.DataFrame, threshold_summary: dict) -> None:
    """Render a simple test-row playback simulation for presentation."""
    st.subheader("Row 시뮬레이션")
    st.caption("실시간 센서 스트리밍은 아니며, test set 예측 결과를 한 row씩 넘겨보는 발표용 시뮬레이션입니다.")

    selected_threshold = float(threshold_summary["selected_threshold"])
    selected_position = st.slider(
        "Test row 선택",
        min_value=0,
        max_value=len(predictions) - 1,
        value=0,
        step=1,
    )

    current = predictions.iloc[selected_position]
    probability = float(current["xgboost_probability"])
    predicted_by_threshold = int(probability >= selected_threshold)
    risk_label = "High Risk" if predicted_by_threshold == 1 else "Normal"
    risk_class = "risk-high" if predicted_by_threshold == 1 else "risk-normal"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("XGBoost Probability", f"{probability:.4f}", "고장 확률")
    with col2:
        metric_card("Selected Threshold", f"{selected_threshold:.2f}", "F1-score 기준")
    with col3:
        metric_card("Actual Failure", str(int(current["actual_machine_failure"])), "실제 정답")
    with col4:
        st.markdown(
            f"""
            <div class="{risk_class}">
                <div style="font-size:0.9rem;">Risk Status</div>
                <div style="font-size:2rem;">{risk_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    row_detail = pd.DataFrame(
        [
            {
                "Simulation Row": selected_position,
                "UDI": current["UDI"],
                "Product ID": current["Product ID"],
                "Actual Failure": int(current["actual_machine_failure"]),
                "XGBoost Probability": round(probability, 4),
                f"XGBoost Prediction by {selected_threshold:.2f}": predicted_by_threshold,
                "Original XGBoost Prediction": int(current["xgboost_prediction"]),
            }
        ]
    )
    st.dataframe(row_detail, width="stretch", hide_index=True)

    window_size = st.slider("최근 N개 row 표시", min_value=10, max_value=200, value=50, step=10)
    start = max(0, selected_position - window_size + 1)
    chart_data = predictions.iloc[start : selected_position + 1].copy()
    chart_data["simulation_row"] = range(start, selected_position + 1)
    chart_data["selected_threshold"] = selected_threshold

    st.line_chart(
        chart_data.set_index("simulation_row")[["xgboost_probability", "selected_threshold"]],
        width="stretch",
    )

    st.info(
        "선이 threshold를 넘으면 High Risk로 표시됩니다. "
        "이 탭은 실제 모델을 새로 돌리는 것이 아니라 저장된 test 결과를 사용해 playback 흐름을 보여줍니다."
    )


def render_realtime_prescription_tab(
    spc_timeseries: pd.DataFrame,
    future_predictions: pd.DataFrame,
    future_metrics: dict,
    threshold_summary: dict,
    spc_summary: dict,
) -> None:
    """Render the simulated real-time forecasting and prescription PoC."""
    st.subheader("실시간 처방 PoC")
    st.caption(
        "AI4I UDI 순서를 실시간 스트림처럼 재생하는 시뮬레이션입니다. "
        "실제 공장 센서 feed가 아니라 최종발표용 simulated real-time forecasting PoC입니다."
    )

    if "realtime_position" not in st.session_state:
        st.session_state["realtime_position"] = 0

    max_position = len(spc_timeseries) - 1
    control_cols = st.columns([1, 1, 1, 2])
    with control_cols[0]:
        if st.button("Reset", key="realtime_reset"):
            st.session_state["realtime_position"] = 0
    with control_cols[1]:
        if st.button("Next row", key="realtime_next"):
            st.session_state["realtime_position"] = min(
                max_position,
                st.session_state["realtime_position"] + 1,
            )
    with control_cols[2]:
        if st.button("Jump risk", key="realtime_jump_risk"):
            st.session_state["realtime_position"] = int(
                future_predictions["predicted_future_max_risk_h10"].idxmax()
            )
    with control_cols[3]:
        selected_position = st.slider(
            "Simulated stream position",
            min_value=0,
            max_value=max_position,
            value=int(st.session_state["realtime_position"]),
            step=1,
        )
        st.session_state["realtime_position"] = selected_position

    selected_row = spc_timeseries.iloc[int(st.session_state["realtime_position"])]
    selected_threshold = float(threshold_summary["selected_threshold"])

    model, feature_columns, explainer = train_stage7_inference_bundle()
    live_features = preprocess_features(
        pd.DataFrame([selected_row.to_dict()]),
        expected_columns=feature_columns,
    )
    current_probability = float(model.predict_proba(live_features)[:, 1][0])
    live_shap_values = calculate_uploaded_shap_values(explainer, live_features)
    factors = top_failure_factors(live_features, live_shap_values, 0)
    future_context = future_prediction_context(
        future_predictions,
        int(selected_row["time_step"]),
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Current Risk", f"{current_probability:.4f}", "XGBoost live inference")
    with col2:
        metric_card(
            "Future Max Risk",
            f"{future_context.get('predicted_future_max_risk_h10', 0):.4f}",
            "next 10 simulated steps",
        )
    with col3:
        metric_card(
            "Future Deviation",
            "Yes" if future_context.get("predicted_future_deviation_h10") else "No",
            f"prob {future_context.get('predicted_future_deviation_probability_h10', 0):.4f}",
        )
    with col4:
        metric_card(
            "Forecast F1",
            f"{future_metrics['classification']['f1_score']:.4f}",
            "chronological validation",
        )

    st.markdown(
        """
        <div class="callout">
        이 탭은 실제 센서 스트리밍을 직접 연결한 것이 아니라, AI4I row를 UDI 순서로 재생하면서
        현재 위험과 미래 10-step 이탈 가능성을 계산하는 발표용 웹 시스템입니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.image(
        str(REQUIRED_FILES["future_chart"]),
        caption="Future 10-step deviation prediction validation chart",
        width="stretch",
    )

    chart_window = st.slider(
        "최근 stream window",
        min_value=20,
        max_value=250,
        value=80,
        step=10,
        key="realtime_window",
    )
    end = int(st.session_state["realtime_position"]) + 1
    start = max(0, end - chart_window)
    chart_data = future_predictions.iloc[start:end].copy()
    chart_data["selected_threshold"] = selected_threshold
    st.line_chart(
        chart_data.set_index("time_step")[
            [
                "xgboost_probability",
                "predicted_future_max_risk_h10",
                "selected_threshold",
            ]
        ],
        width="stretch",
    )

    sensor_columns = [
        "time_step",
        "simulated_timestamp",
        "UDI",
        "Type",
        "Air temperature [K]",
        "Process temperature [K]",
        "Rotational speed [rpm]",
        "Torque [Nm]",
        "Tool wear [min]",
    ]
    st.dataframe(
        pd.DataFrame([selected_row[sensor_columns].to_dict()]),
        width="stretch",
        hide_index=True,
    )

    st.subheader("실시간 SHAP 원인")
    st.dataframe(factors, width="stretch", hide_index=True)
    st.markdown(
        realtime_prescription_note(
            current_probability,
            selected_threshold,
            future_context,
            factors,
        )
    )

    context = realtime_report_context(
        selected_row,
        current_probability,
        selected_threshold,
        future_context,
        spc_summary,
        factors,
    )
    if st.button("현재 row로 LLM/fallback 리포트 생성", type="primary"):
        report, mode = genai_ai_report(context)
        st.info(f"리포트 생성 모드: {mode}")
        st.markdown(report)
        st.download_button(
            "실시간 PoC 리포트 다운로드",
            data=report.encode("utf-8"),
            file_name="realtime_prescription_report.md",
            mime="text/markdown",
        )


def render_field_csv_tab(threshold_summary: dict) -> None:
    """Render Stage 7-lite CSV upload inference and Stage 8-lite note draft."""
    st.subheader("Stage 7-lite 현장 데이터 입력 MVP")
    st.caption(
        "실제 설비 연결은 아니며, 중소기업 현장 CSV를 업로드한다고 가정한 로컬 예측 실험 기능입니다."
    )

    st.markdown(
        """
        이 탭은 발표용 결과뷰어에서 한 단계 더 나아가, 사용자가 가진 센서 CSV를 넣었을 때
        XGBoost 고장 확률과 `High Risk` 여부를 계산하는 PoC입니다.
        """
    )

    expected_columns = pd.DataFrame(
        {
            "필수 컬럼": RAW_UPLOAD_COLUMNS,
            "설명": [
                "제품 타입: L, M, H",
                "공기 온도",
                "공정 온도",
                "회전 속도",
                "토크",
                "공구 마모 시간",
            ],
        }
    )
    st.dataframe(expected_columns, width="stretch", hide_index=True)

    uploaded_file = st.file_uploader(
        "현장 센서 CSV 업로드",
        type=["csv"],
        help="AI4I와 같은 센서 컬럼을 가진 CSV를 업로드하면 로컬에서 예측합니다.",
    )

    if uploaded_file is None:
        st.info("데모용으로는 `data/ai4i2020.csv`와 같은 컬럼 구조의 CSV를 업로드하면 됩니다.")
        return

    try:
        uploaded_df = pd.read_csv(uploaded_file)
        selected_threshold = float(threshold_summary["selected_threshold"])
        model, feature_columns, explainer = train_stage7_inference_bundle()
        features = preprocess_features(uploaded_df, expected_columns=feature_columns)
        probabilities = model.predict_proba(features)[:, 1]
        result_df = uploaded_predictions_dataframe(uploaded_df, probabilities, selected_threshold)
        shap_values = calculate_uploaded_shap_values(explainer, features)
    except Exception as error:
        st.error("업로드 CSV를 예측하는 중 문제가 발생했습니다.")
        st.exception(error)
        return

    high_risk_count = int((result_df["risk_status"] == "High Risk").sum())
    max_probability = float(result_df["xgboost_failure_probability"].max())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Uploaded Rows", str(len(result_df)), "CSV 입력 row 수")
    with col2:
        metric_card("High Risk Rows", str(high_risk_count), "threshold 이상")
    with col3:
        metric_card("Max Probability", f"{max_probability:.4f}", "최고 고장 확률")
    with col4:
        metric_card("Threshold", f"{selected_threshold:.2f}", "Stage 4-lite 기준")

    display_columns = [
        "input_row",
        *[column for column in ID_COLUMNS if column in result_df.columns],
        "xgboost_failure_probability",
        "selected_threshold",
        "risk_status",
    ]
    st.dataframe(
        result_df.sort_values("xgboost_failure_probability", ascending=False)[display_columns],
        width="stretch",
        hide_index=True,
    )

    csv_bytes = result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "예측 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="stage7_uploaded_predictions.csv",
        mime="text/csv",
    )

    st.subheader("Stage 8-lite 자연어 처방 초안")
    row_options = result_df["input_row"].tolist()
    default_row = (
        int(result_df.loc[result_df["risk_status"] == "High Risk", "input_row"].iloc[0])
        if high_risk_count
        else int(result_df.sort_values("xgboost_failure_probability", ascending=False)["input_row"].iloc[0])
    )
    selected_row = st.selectbox(
        "처방 초안으로 볼 row",
        options=row_options,
        index=row_options.index(default_row),
        format_func=lambda row: (
            f"row {row} / prob "
            f"{result_df.loc[result_df['input_row'] == row, 'xgboost_failure_probability'].iloc[0]:.4f}"
        ),
    )

    selected_position = int(result_df.index[result_df["input_row"] == selected_row][0])
    factors = top_failure_factors(features, shap_values, selected_position)
    st.dataframe(factors, width="stretch", hide_index=True)
    st.markdown(prescription_draft(result_df.iloc[selected_position], factors, selected_threshold))


def likely_target_index(columns: list[str]) -> int:
    """Choose a useful default target column for company retraining."""
    target_keywords = ["target", "failure", "fail", "fault", "defect", "quality", "label", "ng", "result", "고장", "불량"]
    for index, column_name in enumerate(columns):
        lowered = str(column_name).lower()
        if any(keyword in lowered for keyword in target_keywords):
            return index
    return max(0, len(columns) - 1)


def likely_id_time_columns(columns: list[str], target_column: str) -> list[str]:
    """Suggest columns that should be preserved but not learned as sensors."""
    id_keywords = ["id", "udi", "asset", "machine", "equipment", "eqp", "time", "date", "timestamp", "lot", "batch"]
    suggested = []
    for column_name in columns:
        lowered = str(column_name).lower()
        if column_name != target_column and any(keyword in lowered for keyword in id_keywords):
            suggested.append(column_name)
    return suggested[:5]


def numeric_like_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    """Find columns that are suitable for unit conversion controls."""
    numeric_columns = []
    for column_name in columns:
        numeric_values = pd.to_numeric(df[column_name], errors="coerce")
        if numeric_values.notna().mean() >= 0.8:
            numeric_columns.append(column_name)
    return numeric_columns


def likely_unit_conversion_columns(columns: list[str]) -> list[str]:
    """Suggest likely Celsius columns for the unit-standardization UI."""
    suggested = []
    for column_name in columns:
        lowered = str(column_name).lower()
        if "celsius" in lowered or lowered.endswith("_c") or "temp_c" in lowered:
            suggested.append(column_name)
    return suggested[:5]


def render_unit_conversion_controls(df: pd.DataFrame, feature_columns: list[str]) -> dict:
    """Render unit conversion controls and return selected transformations."""
    numeric_columns = numeric_like_columns(df, feature_columns)
    if not numeric_columns:
        st.info("숫자형으로 보이는 feature가 없어 단위 변환 설정을 건너뜁니다.")
        return {}

    st.markdown("#### 단위 표준화")
    st.caption("선택하지 않은 숫자 컬럼은 multiplier=1, offset=0으로 그대로 사용합니다.")
    default_columns = likely_unit_conversion_columns(numeric_columns)
    conversion_columns = st.multiselect(
        "단위 변환할 숫자 컬럼",
        options=numeric_columns,
        default=default_columns,
        help="예: Celsius 컬럼을 Kelvin 기준으로 맞추려면 Celsius -> Kelvin preset을 사용합니다.",
    )

    unit_conversions = {}
    for column_name in conversion_columns:
        preset_names = list(UNIT_PRESETS)
        default_preset = "Celsius -> Kelvin" if column_name in default_columns else "No conversion"
        preset = st.selectbox(
            f"{column_name} preset",
            options=preset_names,
            index=preset_names.index(default_preset),
            key=f"company_unit_preset_{column_name}",
        )
        preset_values = UNIT_PRESETS[preset]
        col1, col2 = st.columns(2)
        with col1:
            multiplier = st.number_input(
                f"{column_name} multiplier",
                value=float(preset_values["multiplier"]),
                format="%.6f",
                key=f"company_unit_multiplier_{column_name}",
            )
        with col2:
            offset = st.number_input(
                f"{column_name} offset",
                value=float(preset_values["offset"]),
                format="%.6f",
                key=f"company_unit_offset_{column_name}",
            )
        unit_conversions[column_name] = {
            "preset": preset,
            "multiplier": float(multiplier),
            "offset": float(offset),
        }

    return unit_conversions


def render_company_training_result(result: dict) -> None:
    """Show custom retraining metrics, predictions, SHAP factors, and persistence controls."""
    metrics = result["metrics"]
    threshold_summary = result["threshold_summary"]
    predictions = result["predictions"]
    shap_top_features = result["shap_top_features"]

    xgboost_metrics = metrics["models"]["xgboost"]
    high_risk_count = int((predictions["risk_status"] == "High Risk").sum())
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Rows", str(metrics["source_rows"]), "uploaded company CSV")
    with col2:
        metric_card("Best Model", metrics["best_model_by_pr_auc"], "by PR-AUC")
    with col3:
        metric_card("XGBoost PR-AUC", f"{xgboost_metrics['pr_auc']:.4f}", "company test split")
    with col4:
        metric_card("High Risk Rows", str(high_risk_count), "selected threshold")

    st.markdown("#### 모델 성능")
    metrics_df = pd.DataFrame(metrics["models"]).T.reset_index().rename(columns={"index": "model"})
    st.dataframe(metrics_df, width="stretch", hide_index=True)

    st.markdown("#### Threshold 조정")
    threshold_df = pd.DataFrame(
        [
            {"threshold": "0.50 default", **threshold_summary["default_0_5_metrics"]},
            {
                "threshold": f"{threshold_summary['selected_threshold']:.2f} selected",
                **threshold_summary["selected_metrics"],
            },
        ]
    )
    st.dataframe(threshold_df, width="stretch", hide_index=True)

    st.markdown("#### 예측 결과")
    st.dataframe(predictions.head(50), width="stretch", hide_index=True)
    csv_bytes = predictions.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "회사 데이터 예측 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="custom_company_predictions.csv",
        mime="text/csv",
    )

    st.markdown("#### SHAP 상위 요인")
    st.dataframe(shap_top_features, width="stretch", hide_index=True)
    st.bar_chart(shap_top_features.set_index("feature")["mean_abs_shap"], width="stretch")

    if st.button("로컬 산출물로 저장", type="primary"):
        saved_paths = save_custom_training_outputs(result, COMPANY_OUTPUT_DIR)
        st.success(f"저장 완료: {COMPANY_OUTPUT_DIR}")
        st.dataframe(
            pd.DataFrame(
                [{"artifact": key, "path": value} for key, value in saved_paths.items()]
            ),
            width="stretch",
            hide_index=True,
        )


def render_company_retraining_tab() -> None:
    """Render Stage 14-lite custom company CSV mapping and retraining PoC."""
    st.subheader("Stage 14-lite 회사 데이터 재학습 PoC")
    st.caption(
        "라벨이 있는 회사 CSV를 업로드해 target, ID/time 컬럼, 단위 변환을 지정하고 "
        "회사 데이터 기준 Logistic Regression/XGBoost를 새로 학습합니다."
    )
    st.markdown(
        """
        이 탭은 기존 AI4I 고정 모델을 그대로 쓰는 기능이 아니라, 업로드한 회사 데이터에 맞춰
        모델을 다시 학습하는 로컬 PoC입니다. 라벨 없는 이상탐지, 클라우드 배포, 다중 사용자 운영은 아직 범위 밖입니다.
        """
    )

    uploaded_file = st.file_uploader(
        "라벨이 있는 회사 CSV 업로드",
        type=["csv"],
        key="company_retraining_csv",
        help="고장/불량 여부를 나타내는 target column이 포함된 CSV를 업로드합니다.",
    )
    if uploaded_file is None:
        st.info("데모 검증은 AI4I 데이터를 회사 스키마처럼 바꾼 CSV로 수행됩니다.")
        return

    try:
        uploaded_df = pd.read_csv(uploaded_file)
    except Exception as error:
        st.error("회사 CSV를 읽는 중 문제가 발생했습니다.")
        st.exception(error)
        return

    if uploaded_df.empty:
        st.error("업로드한 CSV에 row가 없습니다.")
        return

    st.markdown("#### 업로드 데이터 미리보기")
    st.dataframe(uploaded_df.head(20), width="stretch")

    columns = uploaded_df.columns.tolist()
    target_column = st.selectbox(
        "Target column",
        options=columns,
        index=likely_target_index(columns),
        help="고장/불량 여부를 나타내는 라벨 컬럼을 선택합니다.",
    )
    id_time_options = [column for column in columns if column != target_column]
    id_time_columns = st.multiselect(
        "ID/time column",
        options=id_time_options,
        default=likely_id_time_columns(columns, target_column),
        help="학습 feature에서는 제외하되 예측 결과 CSV에는 보존할 컬럼입니다.",
    )
    feature_columns = [
        column
        for column in columns
        if column != target_column and column not in id_time_columns
    ]
    if not feature_columns:
        st.error("학습에 사용할 feature column이 없습니다.")
        return

    st.markdown("#### 학습 feature 확인")
    st.dataframe(
        pd.DataFrame({"feature_column": feature_columns}),
        width="stretch",
        hide_index=True,
    )

    unit_conversions = render_unit_conversion_controls(uploaded_df, feature_columns)

    if st.button("회사 데이터로 재학습 실행", type="primary"):
        try:
            with st.spinner("회사 데이터로 모델을 재학습하는 중입니다..."):
                result = train_custom_company_model(
                    uploaded_df,
                    target_column=target_column,
                    id_time_columns=id_time_columns,
                    unit_conversions=unit_conversions,
                )
            st.session_state["company_retraining_result"] = result
            st.success("회사 데이터 재학습이 완료되었습니다.")
        except Exception as error:
            st.error("회사 데이터 재학습 중 문제가 발생했습니다.")
            st.exception(error)
            return

    result = st.session_state.get("company_retraining_result")
    if result is not None:
        render_company_training_result(result)


def artifact_mime_type(path: Path) -> str:
    """Choose a simple browser download MIME type for saved artifacts."""
    if path.suffix == ".csv":
        return "text/csv"
    if path.suffix == ".json":
        return "application/json"
    return "text/markdown"


def render_artifact_downloads() -> None:
    """Render download buttons for the most useful presentation artifacts."""
    artifacts = [
        ("metrics.json", REQUIRED_FILES["metrics"]),
        ("baseline_predictions.csv", REQUIRED_FILES["predictions"]),
        ("spc_timeseries.csv", REQUIRED_FILES["spc_timeseries"]),
        ("future_deviation_predictions.csv", REQUIRED_FILES["future_predictions"]),
        ("future_deviation_metrics.json", REQUIRED_FILES["future_metrics"]),
        ("presentation_summary.md", REQUIRED_FILES["presentation"]),
        ("stage9_field_applicability.md", REQUIRED_FILES["stage9_applicability"]),
        ("stage10_operations_summary.md", REQUIRED_FILES["stage10_operations"]),
        ("stage19_20_operations_design.md", REQUIRED_FILES["stage19_20_design"]),
        ("ai_manager_report.md", REQUIRED_FILES["ai_manager_report"]),
    ]

    for row_start in range(0, len(artifacts), 3):
        columns = st.columns(3)
        for column, (label, path) in zip(columns, artifacts[row_start : row_start + 3]):
            with column:
                st.download_button(
                    label,
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime=artifact_mime_type(path),
                    key=f"download_{path.stem}",
                )


def render_predictive_spc_tab(spc_summary: dict, spc_timeseries: pd.DataFrame) -> None:
    """Render the simulated time-series and Predictive SPC outputs."""
    st.subheader("Predictive SPC 시간축 시뮬레이션")
    st.caption(
        "AI4I는 실제 실시간 센서 스트림이 아니므로 UDI 순서를 가상의 시간축으로 두고, "
        "XGBoost 고장 확률을 risk signal로 사용한 발표용 SPC 시뮬레이션입니다."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Simulated Rows", str(spc_summary["total_rows"]), "UDI 순서 time axis")
    with col2:
        metric_card("High Risk", str(spc_summary["high_risk_count"]), "threshold 이상")
    with col3:
        metric_card("SPC Alerts", str(spc_summary["spc_risk_alert_count"]), "risk limit or threshold")
    with col4:
        metric_card("Risk UCL", f"{spc_summary['risk_ucl']:.4f}", "3-sigma control limit")

    col1, col2 = st.columns(2)
    with col1:
        st.image(
            str(REQUIRED_FILES["spc_risk_chart"]),
            caption="Failure probability trend with threshold and control limit",
            width="stretch",
        )
    with col2:
        st.image(
            str(REQUIRED_FILES["spc_control_chart"]),
            caption="Torque control chart as a SHAP-linked process signal",
            width="stretch",
        )

    st.markdown(
        """
        <div class="callout">
        <strong>최종발표용 표현:</strong>
        여기의 Time-Series는 실제 공장 스트리밍이 아니라 공개 데이터에 시간축을 부여한 시뮬레이션입니다.
        따라서 논문에서는 "real-time deployment"가 아니라 "time-series playback 기반 Predictive SPC PoC"로 설명합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    display_columns = [
        "time_step",
        "simulated_timestamp",
        "UDI",
        "Product ID",
        "actual_machine_failure",
        "xgboost_probability",
        "risk_rolling_mean",
        "selected_threshold",
        "risk_status",
        "spc_risk_alert",
        "Torque [Nm]",
        "torque_beyond_control_limit",
    ]
    high_risk_view = spc_timeseries.sort_values("xgboost_probability", ascending=False)
    st.dataframe(
        high_risk_view[display_columns].head(30),
        width="stretch",
        hide_index=True,
    )


def build_selected_report_context(
    selected_row: pd.Series,
    spc_summary: dict,
    ai_context: dict,
    future_predictions: pd.DataFrame | None = None,
) -> dict:
    """Build a row-specific context for the optional LLM report button."""
    future_context = {}
    if future_predictions is not None:
        future_context = future_prediction_context(
            future_predictions,
            int(selected_row["time_step"]),
        )

    return {
        "report_scope": "manager reference report for final capstone presentation",
        "generated_at": "created from Streamlit dashboard",
        "simulation_note": ai_context.get(
            "simulation_note",
            "AI4I rows are ordered by UDI to simulate a time-series stream.",
        ),
        "row": {
            "time_step": int(selected_row["time_step"]),
            "simulated_timestamp": str(selected_row["simulated_timestamp"]),
            "UDI": int(selected_row["UDI"]),
            "Product ID": str(selected_row["Product ID"]),
            "actual_machine_failure": int(selected_row["actual_machine_failure"]),
            "xgboost_probability": round(float(selected_row["xgboost_probability"]), 6),
            "selected_threshold": round(float(selected_row["selected_threshold"]), 6),
            "risk_status": str(selected_row["risk_status"]),
            "risk_beyond_control_limit": bool(selected_row["risk_beyond_control_limit"]),
            "torque_beyond_control_limit": bool(selected_row["torque_beyond_control_limit"]),
        },
        "sensor_values": {
            "Type": str(selected_row["Type"]),
            "Air temperature [K]": round(float(selected_row["Air temperature [K]"]), 4),
            "Process temperature [K]": round(float(selected_row["Process temperature [K]"]), 4),
            "Rotational speed [rpm]": round(float(selected_row["Rotational speed [rpm]"]), 4),
            "Torque [Nm]": round(float(selected_row["Torque [Nm]"]), 4),
            "Tool wear [min]": round(float(selected_row["Tool wear [min]"]), 4),
        },
        "spc_summary": spc_summary,
        "future_prediction": future_context,
        "top_shap_factors": ai_context.get("top_shap_factors", []),
        "guardrail": ai_context.get(
            "guardrail",
            "Do not write an automatic maintenance order.",
        ),
    }


def render_ai_report_tab(
    spc_summary: dict,
    spc_timeseries: pd.DataFrame,
    future_predictions: pd.DataFrame,
    ai_context: dict,
    saved_report: str,
) -> None:
    """Render saved and optional live GenAI manager reports."""
    st.subheader("GenAI 관리자 참고 리포트")
    st.caption(
        "High Risk 또는 SPC 이상 row를 선택해 관리자 참고용 리포트를 생성합니다. "
        "GEMINI_API_KEY 또는 OPENAI_API_KEY가 없으면 로컬 템플릿 fallback으로 안전하게 동작합니다."
    )

    candidate_rows = spc_timeseries[
        (spc_timeseries["risk_status"] == "High Risk") | spc_timeseries["spc_risk_alert"]
    ].copy()
    if candidate_rows.empty:
        candidate_rows = spc_timeseries.sort_values("xgboost_probability", ascending=False).head(20)
    else:
        candidate_rows = candidate_rows.sort_values("xgboost_probability", ascending=False)

    row_options = candidate_rows["time_step"].astype(int).tolist()
    selected_time_step = st.selectbox(
        "리포트 대상 row",
        options=row_options,
        format_func=lambda step: (
            f"time step {step} / UDI "
            f"{int(candidate_rows.loc[candidate_rows['time_step'] == step, 'UDI'].iloc[0])} / prob "
            f"{float(candidate_rows.loc[candidate_rows['time_step'] == step, 'xgboost_probability'].iloc[0]):.4f}"
        ),
    )
    selected_row = candidate_rows[candidate_rows["time_step"] == selected_time_step].iloc[0]
    context = build_selected_report_context(
        selected_row,
        spc_summary,
        ai_context,
        future_predictions,
    )

    evidence_df = pd.DataFrame(
        [
            {"Item": "UDI", "Value": str(context["row"]["UDI"])},
            {"Item": "Failure probability", "Value": f"{context['row']['xgboost_probability']:.4f}"},
            {"Item": "Threshold", "Value": f"{context['row']['selected_threshold']:.2f}"},
            {"Item": "Risk status", "Value": str(context["row"]["risk_status"])},
            {"Item": "SPC risk limit", "Value": str(context["row"]["risk_beyond_control_limit"])},
            {"Item": "Torque control limit", "Value": str(context["row"]["torque_beyond_control_limit"])},
        ]
    )
    future_context = context.get("future_prediction") or {}
    if future_context:
        evidence_df = pd.concat(
            [
                evidence_df,
                pd.DataFrame(
                    [
                        {
                            "Item": "Future max risk h10",
                            "Value": f"{future_context['predicted_future_max_risk_h10']:.4f}",
                        },
                        {
                            "Item": "Future deviation probability h10",
                            "Value": f"{future_context['predicted_future_deviation_probability_h10']:.4f}",
                        },
                        {
                            "Item": "Future deviation h10",
                            "Value": str(future_context["predicted_future_deviation_h10"]),
                        },
                    ]
                ),
            ],
            ignore_index=True,
        )
    st.dataframe(evidence_df, width="stretch", hide_index=True)

    if st.button("선택 row로 AI 리포트 생성", type="primary"):
        report, mode = genai_ai_report(context)
        st.info(f"리포트 생성 모드: {mode}")
        st.markdown(report)
        st.download_button(
            "생성 리포트 다운로드",
            data=report.encode("utf-8"),
            file_name="selected_ai_manager_report.md",
            mime="text/markdown",
        )
    else:
        st.markdown("### 저장된 기본 리포트")
        st.markdown(saved_report)
        st.download_button(
            "저장된 AI 리포트 다운로드",
            data=saved_report.encode("utf-8"),
            file_name="ai_manager_report.md",
            mime="text/markdown",
        )


def render_stage10_operations_tab(
    metrics: dict,
    threshold_summary: dict,
    predictions: pd.DataFrame,
    stage10_operations: str,
) -> None:
    """Render the Stage 10-lite integrated operations summary."""
    xgboost = metrics["models"]["xgboost"]
    selected_threshold = float(threshold_summary["selected_threshold"])
    high_risk_count = int((predictions["xgboost_probability"] >= selected_threshold).sum())
    actual_failures = int(predictions["actual_machine_failure"].sum())
    max_probability = float(predictions["xgboost_probability"].max())

    st.subheader("Stage 10-lite 운영 요약")
    st.caption("실제 운영 제품이 아니라, 기존 산출물을 한 화면에 묶은 발표용 로컬 통합 MVP입니다.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Model Status", "XGBoost", f"PR-AUC {xgboost['pr_auc']:.4f}")
    with col2:
        metric_card("Threshold", f"{selected_threshold:.2f}", "F1-score 기준")
    with col3:
        metric_card("High Risk Rows", str(high_risk_count), f"test {len(predictions)} rows")
    with col4:
        metric_card("PoC Status", "Local MVP", "SPC + optional LLM")

    operation_df = pd.DataFrame(
        [
            {"Item": "Saved test rows", "Value": str(len(predictions)), "Meaning": "baseline_predictions.csv 기준"},
            {"Item": "Actual failure rows", "Value": str(actual_failures), "Meaning": "test set 실제 고장 라벨"},
            {"Item": "High Risk rows", "Value": str(high_risk_count), "Meaning": "selected threshold 이상"},
            {"Item": "Max probability", "Value": f"{max_probability:.4f}", "Meaning": "가장 위험하게 예측된 row"},
        ]
    )
    st.dataframe(operation_df, width="stretch", hide_index=True)

    st.markdown(
        """
        <div class="callout">
        <strong>Stage 10+ 경계:</strong>
        현재는 AI4I row playback 기반 시간축 시뮬레이션, Predictive SPC chart,
        선택적 LLM 관리자 리포트까지 붙인 로컬 PoC입니다.
        실제 센서 스트리밍, 클라우드 배포, 자동 정비 명령은 최종 발표에서 한계로 분리합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("핵심 산출물 다운로드")
    render_artifact_downloads()

    st.divider()
    st.markdown(stage10_operations)


def render_stage15_20_operations_tab(ai_context: dict) -> None:
    """Render local API, SQLite event history, and work-order decision status."""
    st.subheader("Stage 15~20 로컬 운영 통합 PoC")
    st.caption(
        "file-drop streaming, FastAPI, Stage 19 field-event, SQLite 이력, "
        "Stage 20 operator decision logging을 로컬에서 실제 호출/저장 흐름으로 검증합니다."
    )

    st.markdown(
        """
        <div class="callout">
        <strong>발표 경계:</strong>
        이 탭은 Stage 1~20 로컬 통합 PoC입니다. 실제 PLC/SCADA, MQTT/OPC UA,
        클라우드 배포, 무인 자동 정비 명령이 완료됐다고 주장하지 않습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if OPERATIONS_DB_PATH.exists():
        events = list_prediction_events(limit=25, db_path=OPERATIONS_DB_PATH)
        drafts = list_work_order_drafts(limit=10, db_path=OPERATIONS_DB_PATH)
        decisions = list_work_order_decisions(limit=10, db_path=OPERATIONS_DB_PATH)
    else:
        events = []
        drafts = []
        decisions = []

    field_events = [event for event in events if str(event.get("source", "")).startswith("field_event:")]
    report_mode = str(ai_context.get("report_generation_mode", "not generated"))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("GenAI Report", report_mode.split(":")[0], report_mode)
    with col2:
        metric_card("Field Events", str(len(field_events)), "POST /field-event")
    with col3:
        metric_card("Drafts", str(len(drafts)), "human approval required")
    with col4:
        metric_card("Decisions", str(len(decisions)), "approve/reject/review")

    st.markdown("#### 실행 명령")
    st.code(
        ".\\run_stage1_20_gemini.ps1\n"
        "# OpenAI 경로를 쓰려면 .\\run_stage1_20_openai.ps1\n"
        ".\\.venv\\Scripts\\python.exe -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000\n"
        ".\\.venv\\Scripts\\python.exe src\\verify_stage19_20_integration.py",
        language="powershell",
    )

    st.markdown("#### 최근 예측 이벤트")
    if events:
        event_rows = []
        for event in events:
            top_factor = event.get("top_shap_factors", [{}])[0].get("feature", "")
            event_input = event.get("input", {})
            event_rows.append(
                {
                    "created_at": event["created_at"],
                    "source": event["source"],
                    "equipment_id": event_input.get("equipment_id", ""),
                    "event_timestamp": event_input.get("event_timestamp", ""),
                    "event_id": event["event_id"],
                    "probability": event["probability"],
                    "threshold": event["threshold"],
                    "risk_status": event["risk_status"],
                    "top_factor": top_factor,
                }
            )
        st.dataframe(pd.DataFrame(event_rows), width="stretch", hide_index=True)
    else:
        st.info("아직 `outputs/operations.db`에 저장된 예측 이벤트가 없습니다.")

    st.markdown("#### 최근 작업지시 초안")
    if drafts:
        draft_rows = [
            {
                "created_at": draft["created_at"],
                "draft_id": draft["draft_id"],
                "event_id": draft["event_id"],
                "mode": draft["generation_mode"],
                "requires_human_approval": draft["draft_json"].get("requires_human_approval"),
                "draft_path": draft["draft_path"],
            }
            for draft in drafts
        ]
        st.dataframe(pd.DataFrame(draft_rows), width="stretch", hide_index=True)
        selected_draft = st.selectbox(
            "작업지시 초안 미리보기",
            options=drafts,
            format_func=lambda draft: f"{draft['created_at']} / {draft['draft_id']}",
        )
        st.markdown(selected_draft["markdown"])
    else:
        st.info("아직 생성된 작업지시 초안이 없습니다.")

    st.markdown("#### Stage 20 operator decision 기록")
    if decisions:
        decision_rows = [
            {
                "created_at": decision["created_at"],
                "decision_id": decision["decision_id"],
                "draft_id": decision["draft_id"],
                "event_id": decision["event_id"],
                "operator_id": decision["operator_id"],
                "decision": decision["decision"],
                "note": decision["note"],
            }
            for decision in decisions
        ]
        st.dataframe(pd.DataFrame(decision_rows), width="stretch", hide_index=True)
        if WORK_ORDER_DECISIONS_PATH.exists():
            st.download_button(
                "work_order_decisions.csv 다운로드",
                data=WORK_ORDER_DECISIONS_PATH.read_bytes(),
                file_name="work_order_decisions.csv",
                mime="text/csv",
            )
    else:
        st.info("아직 Stage 20 operator decision 기록이 없습니다.")

    st.markdown("#### Stage 15~20 아키텍처 문서")
    if STAGE15_20_ARCHITECTURE_PATH.exists():
        st.markdown(STAGE15_20_ARCHITECTURE_PATH.read_text(encoding="utf-8"))
    else:
        st.info("`src\\verify_stage19_20_integration.py` 실행 후 문서가 생성됩니다.")


def render_markdown_tab(title: str, markdown_text: str) -> None:
    """Render a Markdown output file inside a tab."""
    st.subheader(title)
    st.markdown(markdown_text)


def main() -> None:
    """Run the Streamlit read-only results dashboard."""
    configure_page()
    render_header()

    missing_files = [path for path in REQUIRED_FILES.values() if not path.exists()]
    if missing_files:
        show_missing_files(missing_files)
        st.stop()

    metrics = load_json(REQUIRED_FILES["metrics"])
    threshold_summary = load_json(REQUIRED_FILES["threshold"])
    local_case = load_markdown(REQUIRED_FILES["local_case"])
    presentation_summary = load_markdown(REQUIRED_FILES["presentation"])
    research_plan = load_markdown(REQUIRED_FILES["research_plan"])
    midterm_guide = load_markdown(REQUIRED_FILES["midterm_guide"])
    midterm_qna = load_markdown(REQUIRED_FILES["midterm_qna"])
    rehearsal_checklist = load_markdown(REQUIRED_FILES["rehearsal_checklist"])
    backup_checklist = load_markdown(REQUIRED_FILES["backup_checklist"])
    final_roadmap = load_markdown(REQUIRED_FILES["final_roadmap"])
    stage9_applicability = load_markdown(REQUIRED_FILES["stage9_applicability"])
    stage10_operations = load_markdown(REQUIRED_FILES["stage10_operations"])
    stage19_20_design = load_markdown(REQUIRED_FILES["stage19_20_design"])
    predictions = load_predictions(REQUIRED_FILES["predictions"])
    spc_timeseries = load_csv(REQUIRED_FILES["spc_timeseries"])
    spc_summary = load_json(REQUIRED_FILES["spc_summary"])
    future_predictions = load_csv(REQUIRED_FILES["future_predictions"])
    future_metrics = load_json(REQUIRED_FILES["future_metrics"])
    ai_context = load_json(REQUIRED_FILES["ai_report_context"])
    ai_manager_report = load_markdown(REQUIRED_FILES["ai_manager_report"])

    tabs = st.tabs(
        [
            "성과 요약",
            "모델 비교",
            "Threshold 조정",
            "SHAP 해석",
            "Row 시뮬레이션",
            "실시간 처방 PoC",
            "Predictive SPC",
            "AI Report",
            "현장 CSV MVP",
            "회사 데이터 재학습 PoC",
            "개별 사례",
            "중간발표 진행안",
            "예상 질문",
            "발표 요약",
            "연구계획",
            "리허설 체크리스트",
            "당일 백업",
            "Stage 9 실제 적용성",
            "Stage 10 운영 요약",
            "Stage 15~20 로컬 통합",
            "Stage 19~20 운영 설계",
            "최종 단계 로드맵",
        ]
    )

    with tabs[0]:
        render_summary_tab(metrics, threshold_summary)
    with tabs[1]:
        render_model_tab(metrics)
    with tabs[2]:
        render_threshold_tab(threshold_summary)
    with tabs[3]:
        render_shap_tab()
    with tabs[4]:
        render_row_simulation_tab(predictions, threshold_summary)
    with tabs[5]:
        render_realtime_prescription_tab(
            spc_timeseries,
            future_predictions,
            future_metrics,
            threshold_summary,
            spc_summary,
        )
    with tabs[6]:
        render_predictive_spc_tab(spc_summary, spc_timeseries)
    with tabs[7]:
        render_ai_report_tab(
            spc_summary,
            spc_timeseries,
            future_predictions,
            ai_context,
            ai_manager_report,
        )
    with tabs[8]:
        render_field_csv_tab(threshold_summary)
    with tabs[9]:
        render_company_retraining_tab()
    with tabs[10]:
        render_markdown_tab("개별 고장 예측 사례", local_case)
    with tabs[11]:
        render_markdown_tab("PPT 없는 중간발표 진행안", midterm_guide)
    with tabs[12]:
        render_markdown_tab("5월 11일 중간발표 예상 질문 답변", midterm_qna)
    with tabs[13]:
        render_markdown_tab("5월 11일 발표 요약", presentation_summary)
    with tabs[14]:
        render_markdown_tab("캡스톤 연구 Stage 보완안", research_plan)
    with tabs[15]:
        render_markdown_tab("5월 11일 대시보드 리허설 체크리스트", rehearsal_checklist)
    with tabs[16]:
        render_markdown_tab("발표 당일 백업 체크리스트", backup_checklist)
    with tabs[17]:
        render_markdown_tab("Stage 9 실제 적용성 정리", stage9_applicability)
    with tabs[18]:
        render_stage10_operations_tab(metrics, threshold_summary, predictions, stage10_operations)
    with tabs[19]:
        render_stage15_20_operations_tab(ai_context)
    with tabs[20]:
        render_markdown_tab("Stage 19~20 운영 설계", stage19_20_design)
    with tabs[21]:
        render_markdown_tab("최종 단계 로드맵", final_roadmap)


if __name__ == "__main__":
    main()
