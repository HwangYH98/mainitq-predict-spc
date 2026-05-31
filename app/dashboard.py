import json
import hmac
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime
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
LOCAL_NOTES_DIR = PROJECT_ROOT / "local_presentation_notes"

if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from company_adapter import (
    UNIT_PRESETS,
    save_custom_training_outputs,
    train_custom_company_model,
)
from data import ID_COLUMNS, preprocess_features, prepare_train_test_data
from operations_store import (
    insert_audit_log,
    list_audit_logs,
    list_prediction_events,
    list_work_order_decisions,
    list_work_order_drafts,
)
from predictive_spc import genai_ai_report
from preprocessing_prediction_engine import (
    CANONICAL_SENSOR_COLUMNS,
    NUMERIC_SENSOR_COLUMNS,
    UNIT_OPTIONS,
    infer_column_mapping,
    predict_company_sensor_csv,
    sample_company_alias_dataframe,
)
from realtime_ops import (
    create_work_order_decision,
    create_work_order_draft,
    predict_field_event,
)
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

OPTIONAL_FILES = {
    "model_strategy_summary": OUTPUT_DIR / "model_strategy_summary.md",
    "model_strategy_comparison": OUTPUT_DIR / "model_strategy_comparison.csv",
    "model_strategy_pr_curve": OUTPUT_DIR / "model_strategy_pr_curve.png",
    "spc_vs_ml_summary": OUTPUT_DIR / "spc_vs_ml_summary.md",
    "spc_vs_ml_comparison": OUTPUT_DIR / "spc_vs_ml_comparison.csv",
    "mock_bridge_summary": OUTPUT_DIR / "mock_field_bridge_summary.md",
    "operational_value_summary": OUTPUT_DIR / "operational_value_simulation.md",
    "operational_value_comparison": OUTPUT_DIR / "operational_value_simulation.csv",
    "operational_value_chart": OUTPUT_DIR / "operational_value_simulation.png",
    "product_capability_summary": OUTPUT_DIR / "product_capability_comparison.md",
    "product_capability_comparison": OUTPUT_DIR / "product_capability_comparison.csv",
    "workflow_traceability_summary": OUTPUT_DIR / "workflow_traceability_summary.md",
    "workflow_traceability_comparison": OUTPUT_DIR / "workflow_traceability_summary.csv",
    "thesis_evidence_pack": OUTPUT_DIR / "thesis_evidence_pack.md",
    "industrial_engineering_evidence": OUTPUT_DIR / "industrial_engineering_evidence.md",
    "company_input_quality_report": OUTPUT_DIR / "company_input_quality_report.csv",
    "company_preprocessing_report": OUTPUT_DIR / "company_preprocessing_report.md",
    "probability_calibration_metrics": OUTPUT_DIR / "probability_calibration_metrics.json",
    "probability_calibration_curve": OUTPUT_DIR / "probability_calibration_curve.png",
    "prediction_confidence_report": OUTPUT_DIR / "prediction_confidence_report.md",
    "operating_policy_thresholds": OUTPUT_DIR / "operating_policy_thresholds.json",
    "company_prediction_results": OUTPUT_DIR / "company_prediction_results.csv",
    "company_risk_priority_queue": OUTPUT_DIR / "company_risk_priority_queue.csv",
    "operating_policy_simulation": OUTPUT_DIR / "operating_policy_simulation.md",
    "open_industrial_validation_metrics": OUTPUT_DIR / "open_industrial_validation_metrics.csv",
    "open_industrial_validation_report": OUTPUT_DIR / "open_industrial_validation_report.md",
    "open_industrial_cost_simulation": OUTPUT_DIR / "open_industrial_cost_simulation.csv",
    "open_industrial_lead_time_report": OUTPUT_DIR / "open_industrial_lead_time_report.md",
    "open_industrial_lead_time_chart": OUTPUT_DIR / "open_industrial_lead_time_chart.png",
    "public_industrial_validation_metrics": OUTPUT_DIR / "public_industrial_validation_metrics.csv",
    "public_industrial_lead_time_metrics": OUTPUT_DIR / "public_industrial_lead_time_metrics.csv",
    "public_industrial_cost_simulation": OUTPUT_DIR / "public_industrial_cost_simulation.csv",
    "public_industrial_rul_metrics": OUTPUT_DIR / "public_industrial_rul_metrics.csv",
    "public_industrial_validation_report": OUTPUT_DIR / "public_industrial_validation_report.md",
    "public_benchmark_claims": OUTPUT_DIR / "public_benchmark_claims.md",
    "public_industrial_lead_time_chart": OUTPUT_DIR / "public_industrial_lead_time_chart.png",
    "public_industrial_cost_chart": OUTPUT_DIR / "public_industrial_cost_chart.png",
    "public_industrial_rul_chart": OUTPUT_DIR / "public_industrial_rul_chart.png",
    "public_industrial_confusion_matrix": OUTPUT_DIR / "public_industrial_confusion_matrix.png",
    "scania_official_cost_metrics": OUTPUT_DIR / "scania_official_cost_metrics.csv",
    "scania_official_cost_report": OUTPUT_DIR / "scania_official_cost_report.md",
    "scania_official_cost_chart": OUTPUT_DIR / "scania_official_cost_comparison.png",
    "scania_official_confusion_matrix": OUTPUT_DIR / "scania_official_confusion_matrix.png",
    "field_validation_protocol": OUTPUT_DIR / "field_validation_protocol.md",
    "field_data_template": OUTPUT_DIR / "field_data_template.csv",
    "field_maintenance_template": OUTPUT_DIR / "field_maintenance_template.csv",
    "field_cost_template": OUTPUT_DIR / "field_cost_template.csv",
    "field_validation_data_request_kit": OUTPUT_DIR / "field_validation_data_request_kit.zip",
    "field_validation_report": OUTPUT_DIR / "field_validation_report.md",
    "field_validation_report_csv": OUTPUT_DIR / "field_validation_report.csv",
    "field_validation_report_json": OUTPUT_DIR / "field_validation_report.json",
}

LOCAL_NOTE_FILES = {
    "presentation_talk_track": LOCAL_NOTES_DIR / "presentation_talk_track.md",
    "thesis_claims_and_limits": LOCAL_NOTES_DIR / "thesis_claims_and_limits.md",
    "industrial_engineering_notes": LOCAL_NOTES_DIR / "industrial_engineering_notes.md",
    "github_upload_checklist": LOCAL_NOTES_DIR / "github_upload_checklist.md",
}

RAW_UPLOAD_COLUMNS = [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]

SAMPLE_FIELD_ROWS = [
    {
        "Type": "L",
        "Air temperature [K]": 298.1,
        "Process temperature [K]": 308.6,
        "Rotational speed [rpm]": 1551,
        "Torque [Nm]": 42.8,
        "Tool wear [min]": 0,
    },
    {
        "Type": "M",
        "Air temperature [K]": 298.2,
        "Process temperature [K]": 308.7,
        "Rotational speed [rpm]": 1408,
        "Torque [Nm]": 46.3,
        "Tool wear [min]": 3,
    },
    {
        "Type": "H",
        "Air temperature [K]": 299.4,
        "Process temperature [K]": 309.2,
        "Rotational speed [rpm]": 1320,
        "Torque [Nm]": 58.2,
        "Tool wear [min]": 120,
    },
]

STAGE19_SENSOR_PRESETS = {
    "Normal 샘플": {
        "Type": "L",
        "Air temperature [K]": 298.1,
        "Process temperature [K]": 308.6,
        "Rotational speed [rpm]": 1551,
        "Torque [Nm]": 42.8,
        "Tool wear [min]": 0,
    },
    "High Risk 샘플": {
        "Type": "L",
        "Air temperature [K]": 302.5,
        "Process temperature [K]": 312.2,
        "Rotational speed [rpm]": 1280,
        "Torque [Nm]": 68.0,
        "Tool wear [min]": 240,
    },
}

GENAI_DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash",
    "openai": "gpt-5.2",
}

GENAI_ENV_KEYS = [
    "AI_REPORT_PROVIDER",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_MODEL_CANDIDATES",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_MODEL_CANDIDATES",
    "REQUIRE_GENAI_REPORT",
    "REQUIRE_OPENAI_REPORT",
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


def configure_page(page_title: str = "AI 예지보전 운영 대시보드") -> None:
    """Set page metadata and product-style dashboard styling."""
    st.set_page_config(
        page_title=page_title,
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
            letter-spacing: 0;
        }
        .hero p {
            color: var(--muted);
            font-size: 1.05rem;
            margin: 0;
        }
        .app-badge {
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
            letter-spacing: 0;
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
def load_optional_markdown(path: Path) -> str:
    """Load an optional Markdown artifact when it exists."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


@st.cache_data
def load_predictions(path: Path) -> pd.DataFrame:
    """Load saved test-set predictions for the row simulation tab."""
    return pd.read_csv(path)


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    """Load a saved CSV artifact."""
    return pd.read_csv(path)


def sample_field_dataframe() -> pd.DataFrame:
    """Return a small AI4I-compatible CSV example for dashboard users."""
    return pd.DataFrame(SAMPLE_FIELD_ROWS)


def validate_sensor_upload(uploaded_df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned sensor upload or raise a user-friendly ValueError."""
    missing_columns = [column for column in RAW_UPLOAD_COLUMNS if column not in uploaded_df.columns]
    if missing_columns:
        raise ValueError(
            "필수 컬럼이 없습니다: "
            + ", ".join(missing_columns)
            + ". 샘플 CSV의 컬럼명을 그대로 맞춰 주세요."
        )

    cleaned = uploaded_df.copy()
    cleaned["Type"] = cleaned["Type"].astype(str).str.strip().str.upper()
    invalid_types = sorted(set(cleaned.loc[~cleaned["Type"].isin(["L", "M", "H"]), "Type"]))
    if invalid_types:
        raise ValueError("Type 컬럼은 L, M, H 중 하나여야 합니다. 발견된 값: " + ", ".join(invalid_types))

    numeric_columns = [column for column in RAW_UPLOAD_COLUMNS if column != "Type"]
    for column in numeric_columns:
        converted = pd.to_numeric(cleaned[column], errors="coerce")
        if converted.isna().any():
            bad_rows = (converted[converted.isna()].index + 1).astype(str).tolist()[:5]
            raise ValueError(
                f"{column} 컬럼은 숫자여야 합니다. 숫자로 바꿀 수 없는 row: "
                + ", ".join(bad_rows)
            )
        cleaned[column] = converted

    return cleaned


def csv_download_bytes(df: pd.DataFrame) -> bytes:
    """Return UTF-8-SIG bytes so Excel opens Korean/CSV files cleanly."""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def get_secret_value(*names: str) -> str:
    """Read a password-like value from env vars or Streamlit secrets."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value

    try:
        secrets = st.secrets
    except Exception:
        return ""

    for name in names:
        try:
            value = secrets.get(name)
        except Exception:
            value = None
        if value:
            return str(value)

        if "." in name:
            current = secrets
            try:
                for part in name.split("."):
                    current = current[part]
            except Exception:
                current = None
            if current:
                return str(current)

    return ""


def configured_password_for_role(role: str) -> str:
    """Return the configured password for one dashboard role."""
    if role == "admin":
        return get_secret_value("APP_ADMIN_PASSWORD", "auth.admin_password")
    return get_secret_value("APP_OPERATOR_PASSWORD", "auth.operator_password")


def current_actor() -> dict:
    """Return the authenticated session actor, or a safe anonymous fallback."""
    return st.session_state.get(
        "auth_user",
        {"actor_id": "anonymous", "role": "anonymous"},
    )


def record_audit(
    action: str,
    status: str,
    target_type: str = "",
    target_id: str = "",
    detail: dict | None = None,
    error_message: str = "",
    actor: dict | None = None,
) -> None:
    """Append an audit log without breaking the user flow if logging fails."""
    actor = actor or current_actor()
    entry = {
        "audit_id": str(uuid.uuid4()),
        "created_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "actor_id": actor.get("actor_id", "anonymous"),
        "role": actor.get("role", "anonymous"),
        "action": action,
        "status": status,
        "target_type": target_type,
        "target_id": target_id,
        "detail": detail or {},
        "error_message": error_message,
    }
    try:
        insert_audit_log(entry, db_path=OPERATIONS_DB_PATH)
    except Exception as error:
        st.sidebar.warning(f"Audit log write failed: {error}")


def require_login(role: str) -> dict:
    """Require an operator/admin password without storing credentials in code."""
    session_key = f"{role}_authenticated"
    existing_user = st.session_state.get("auth_user")
    if st.session_state.get(session_key) and existing_user and existing_user.get("role") == role:
        return existing_user

    password = configured_password_for_role(role)
    role_label = "Admin" if role == "admin" else "Operator"
    if not password:
        st.error(f"{role_label} password is not configured.")
        st.markdown(
            "환경변수 또는 Streamlit secrets에 비밀번호를 설정한 뒤 다시 실행하세요. "
            "비밀번호는 코드나 Git에 저장하지 않습니다."
        )
        if role == "admin":
            st.code('$env:APP_ADMIN_PASSWORD="your-admin-password"', language="powershell")
        else:
            st.code('$env:APP_OPERATOR_PASSWORD="your-operator-password"', language="powershell")
        st.stop()

    st.subheader(f"{role_label} 로그인")
    st.caption("비밀번호는 현재 세션 인증에만 사용하며 파일에 저장하지 않습니다.")
    with st.form(f"{role}_login_form"):
        actor_id = st.text_input(
            "사용자 ID",
            value="admin" if role == "admin" else "operator_01",
            key=f"{role}_login_actor_id",
        )
        supplied = st.text_input(
            "비밀번호",
            type="password",
            key=f"{role}_login_password",
        )
        submitted = st.form_submit_button("로그인", type="primary")

    if submitted:
        actor = {"actor_id": actor_id.strip() or role, "role": role}
        if hmac.compare_digest(supplied, password):
            st.session_state[session_key] = True
            st.session_state["auth_user"] = actor
            record_audit("auth.login", "success", "session", role, actor=actor)
            st.success("로그인되었습니다.")
            st.rerun()
        record_audit(
            "auth.login",
            "failure",
            "session",
            role,
            error_message="invalid password",
            actor=actor,
        )
        st.error("비밀번호가 맞지 않습니다.")

    st.stop()


def render_genai_sidebar_settings() -> dict:
    """Collect optional GenAI settings in the sidebar without persisting secrets."""
    st.sidebar.markdown("### GenAI API 설정")
    provider_label = st.sidebar.radio(
        "리포트 API",
        options=["Gemini", "OpenAI"],
        index=0,
        horizontal=True,
        help="관리자 참고 리포트를 새로 생성할 때 사용할 API입니다.",
        key="genai_provider_label",
    )
    provider = provider_label.lower()
    model_key = f"genai_{provider}_model"
    st.session_state.setdefault(model_key, GENAI_DEFAULT_MODELS[provider])
    model = st.sidebar.text_input(
        "모델",
        key=model_key,
        help="기본값을 그대로 사용해도 됩니다.",
    ).strip()
    api_key = st.sidebar.text_input(
        f"{provider_label} API key",
        type="password",
        key=f"genai_{provider}_api_key",
        help="파일에 저장하지 않고 현재 Streamlit 세션에서만 사용합니다.",
    ).strip()

    st.sidebar.caption("API key는 파일, .env, Git 기록에 저장하지 않습니다.")
    if api_key:
        st.sidebar.success(f"{provider_label} key 입력됨")
    else:
        st.sidebar.info("API key 없음: 저장된 리포트만 표시")

    return {
        "provider": provider,
        "provider_label": provider_label,
        "model": model or GENAI_DEFAULT_MODELS[provider],
        "api_key": api_key,
        "has_key": bool(api_key),
    }


def genai_status_text(settings: dict) -> str:
    """Return a short user-facing status for the selected GenAI provider."""
    if settings.get("has_key"):
        return f"{settings['provider_label']} key 입력됨 / model {settings['model']}"
    return "API key 없음: 저장된 리포트만 표시"


def summarize_report_mode(report_mode: str) -> tuple[str, str]:
    """Translate internal report mode values into product-friendly labels."""
    mode = str(report_mode or "not generated")
    if mode.startswith("gemini_generate_content"):
        return "생성됨", "Gemini 기반"
    if mode.startswith("openai_responses_api"):
        return "생성됨", "OpenAI 기반"
    if mode.startswith("fallback"):
        return "저장 리포트", "API key 없이 저장본 표시"
    if mode in {"not generated", "", "none"}:
        return "미생성", "API key 입력 후 생성 가능"
    return "저장 리포트", "상세 모드는 Admin에서 확인"


def genai_report_with_sidebar_settings(context: dict, settings: dict) -> tuple[str, str]:
    """Generate a report with sidebar key/model using temporary environment variables."""
    if not settings.get("has_key"):
        return genai_ai_report(context, require_genai=False)

    previous_env = {key: os.environ.get(key) for key in GENAI_ENV_KEYS}
    try:
        provider = settings["provider"]
        model = settings["model"]
        os.environ["AI_REPORT_PROVIDER"] = provider
        os.environ["REQUIRE_GENAI_REPORT"] = "1"
        if provider == "gemini":
            os.environ["GEMINI_API_KEY"] = settings["api_key"]
            os.environ["GEMINI_MODEL"] = model
            os.environ["GEMINI_MODEL_CANDIDATES"] = f"{model},gemini-2.5-flash,gemini-2.5-flash-lite"
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ["REQUIRE_OPENAI_REPORT"] = "0"
        else:
            os.environ["OPENAI_API_KEY"] = settings["api_key"]
            os.environ["OPENAI_MODEL"] = model
            os.environ["OPENAI_MODEL_CANDIDATES"] = f"{model},gpt-5-mini,gpt-5-nano,gpt-4.1-mini,gpt-4o-mini"
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ["REQUIRE_OPENAI_REPORT"] = "1"
        return genai_ai_report(context, require_genai=True)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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
        "주의: 이 문장은 실제 LLM 호출이 아니라 SHAP 근거를 사용한 관리자 참고 권고입니다. "
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


def render_header(
    badge: str = "운영 대시보드",
    title: str = "AI 예지보전 운영 대시보드",
    subtitle: str = (
        "센서 CSV를 기반으로 고장 확률, 위험 우선순위, AI 리포트, 작업지시 이력을 관리합니다."
    ),
) -> None:
    """Render dashboard title and badge."""
    st.markdown(
        f"""
        <div class="hero">
            <div class="app-badge">{badge}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
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
    """Render CSV upload inference and a manager-facing evidence note."""
    st.subheader("센서 CSV 업로드 예측")
    st.caption(
        "샘플 형식에 맞춘 센서 데이터를 넣으면 row별 고장 확률과 High Risk 여부를 바로 계산합니다."
    )

    st.markdown(
        """
        사용자는 샘플 형식에 맞춘 센서 CSV만 업로드하면 됩니다.
        시스템은 전처리, XGBoost 확률 예측, threshold 판정, 주요 위험 요인 요약을 순서대로 수행합니다.
        """
    )

    st.markdown("#### 입력 순서")
    st.dataframe(
        pd.DataFrame(
            [
                {"순서": 1, "사용자 행동": "샘플 CSV 다운로드", "시스템 역할": "필수 컬럼과 예시값을 보여줌"},
                {"순서": 2, "사용자 행동": "센서 CSV 업로드", "시스템 역할": "컬럼명, Type 값, 숫자 형식을 확인"},
                {"순서": 3, "사용자 행동": "결과 확인", "시스템 역할": "고장 확률, High Risk 여부, 그래프, CSV 다운로드 제공"},
            ]
        ),
        width="stretch",
        hide_index=True,
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
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 필수 컬럼")
        st.dataframe(expected_columns, width="stretch", hide_index=True)
    with col2:
        st.markdown("#### 실제 예시 3행")
        st.dataframe(sample_field_dataframe(), width="stretch", hide_index=True)

    sample_df = sample_field_dataframe()
    st.download_button(
        "샘플 CSV 다운로드",
        data=csv_download_bytes(sample_df),
        file_name="sample_field_sensor_rows.csv",
        mime="text/csv",
        help="업로드 형식을 확인하거나 즉시 테스트할 때 사용할 수 있는 예시 파일입니다.",
    )

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
        uploaded_df = validate_sensor_upload(uploaded_df)
        selected_threshold = float(threshold_summary["selected_threshold"])
        model, feature_columns, explainer = train_stage7_inference_bundle()
        features = preprocess_features(uploaded_df, expected_columns=feature_columns)
        probabilities = model.predict_proba(features)[:, 1]
        result_df = uploaded_predictions_dataframe(uploaded_df, probabilities, selected_threshold)
        shap_values = calculate_uploaded_shap_values(explainer, features)
    except Exception as error:
        record_audit(
            "csv.predict",
            "failure",
            "upload",
            getattr(uploaded_file, "name", "uploaded_csv"),
            error_message=str(error),
        )
        st.error("업로드 CSV를 예측하는 중 문제가 발생했습니다.")
        st.warning(
            "확인할 것: 필수 컬럼 누락, 컬럼명 오타, Type 값(L/M/H), 숫자 컬럼의 문자 입력 여부."
        )
        st.code(str(error), language="text")
        return

    high_risk_count = int((result_df["risk_status"] == "High Risk").sum())
    max_probability = float(result_df["xgboost_failure_probability"].max())
    record_audit(
        "csv.predict",
        "success",
        "upload",
        getattr(uploaded_file, "name", "uploaded_csv"),
        {
            "row_count": int(len(result_df)),
            "high_risk_count": high_risk_count,
            "max_probability": round(max_probability, 6),
        },
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Uploaded Rows", str(len(result_df)), "CSV 입력 row 수")
    with col2:
        metric_card("High Risk Rows", str(high_risk_count), "threshold 이상")
    with col3:
        metric_card("Max Probability", f"{max_probability:.4f}", "최고 고장 확률")
    with col4:
        metric_card("Threshold", f"{selected_threshold:.2f}", "선택 기준")

    display_columns = [
        "input_row",
        *[column for column in ID_COLUMNS if column in result_df.columns],
        "xgboost_failure_probability",
        "selected_threshold",
        "risk_status",
    ]

    st.markdown("#### 업로드 row별 고장 확률 그래프")
    chart_df = result_df[["input_row", "xgboost_failure_probability"]].copy()
    chart_df = chart_df.set_index("input_row")
    st.bar_chart(chart_df, height=320)
    st.caption(f"High Risk 기준 threshold: {selected_threshold:.2f}")

    st.markdown("#### 예측 결과표")
    st.dataframe(
        result_df.sort_values("xgboost_failure_probability", ascending=False)[display_columns],
        width="stretch",
        hide_index=True,
    )

    csv_bytes = result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "예측 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="uploaded_sensor_predictions.csv",
        mime="text/csv",
    )

    st.subheader("선택 row 위험요인과 참고 권고")
    row_options = result_df["input_row"].tolist()
    default_row = (
        int(result_df.loc[result_df["risk_status"] == "High Risk", "input_row"].iloc[0])
        if high_risk_count
        else int(result_df.sort_values("xgboost_failure_probability", ascending=False)["input_row"].iloc[0])
    )
    selected_row = st.selectbox(
        "위험요인으로 볼 row",
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


def render_field_csv_tab(threshold_summary: dict) -> None:
    """Render a company CSV wizard with mapping, quality, calibrated prediction, and priority."""
    st.subheader("데이터 예측")
    st.caption(
        "회사별 CSV를 업로드하면 컬럼 자동 매핑, 단위 변환, 품질 진단, 보정 확률, 위험 우선순위를 한 흐름으로 확인합니다."
    )

    step_col1, step_col2, step_col3, step_col4 = st.columns(4)
    with step_col1:
        metric_card("1. 샘플 다운로드", "확인", "기본/회사형 예시")
    with step_col2:
        metric_card("2. CSV 업로드", "입력", "센서 row 파일")
    with step_col3:
        metric_card("3. 컬럼 확인", "매핑", "단위·결측 점검")
    with step_col4:
        metric_card("4. 예측 실행", "출력", "확률·우선순위")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 1. 기본 센서 샘플")
        ai4i_sample = sample_field_dataframe()
        st.dataframe(ai4i_sample, width="stretch", hide_index=True)
        st.download_button(
            "기본 센서 샘플 CSV 다운로드",
            data=csv_download_bytes(ai4i_sample),
            file_name="sample_ai4i_sensor_rows.csv",
            mime="text/csv",
        )
    with col2:
        st.markdown("#### 1. 회사형 샘플")
        company_sample = sample_company_alias_dataframe()
        st.dataframe(company_sample, width="stretch", hide_index=True)
        st.download_button(
            "회사형 샘플 CSV 다운로드",
            data=csv_download_bytes(company_sample),
            file_name="sample_company_sensor_rows.csv",
            mime="text/csv",
        )

    with st.expander("CSV 형식과 처리 흐름 자세히 보기"):
        st.dataframe(
            pd.DataFrame(
                [
                    {"단계": 1, "이름": "샘플 다운로드", "출력": "필요한 센서 컬럼 구조 확인"},
                    {"단계": 2, "이름": "CSV 업로드", "출력": "원본 데이터 미리보기"},
                    {"단계": 3, "이름": "컬럼 확인", "출력": "회사 컬럼을 기준 센서 컬럼으로 연결"},
                    {"단계": 4, "이름": "예측 실행", "출력": "고장 확률, 위험 판정, 위험 우선순위"},
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "필수 센서": CANONICAL_SENSOR_COLUMNS,
                    "설명": [
                        "제품 또는 운전 조건 등급",
                        "공기 온도",
                        "공정 온도",
                        "회전 속도",
                        "토크",
                        "공구 마모 시간",
                    ],
                }
            ),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 2. CSV 업로드")
    uploaded_file = st.file_uploader(
        "회사/현장 센서 CSV 업로드",
        type=["csv"],
        help="컬럼명이 달라도 자동 매핑 후보를 먼저 보여줍니다. 필요하면 아래에서 직접 수정할 수 있습니다.",
        key="smart_company_csv_upload",
    )

    if uploaded_file is None:
        st.info("샘플 CSV를 내려받아 구조를 확인한 뒤 업로드하세요. API key는 예측에는 필요 없고 AI 리포트 생성에만 필요합니다.")
        return

    try:
        uploaded_df = pd.read_csv(uploaded_file)
    except Exception as error:
        st.error("CSV 파일을 읽는 중 문제가 발생했습니다.")
        st.code(str(error), language="text")
        return

    if uploaded_df.empty:
        st.error("업로드한 CSV에 row가 없습니다.")
        return

    st.markdown("#### 3. 업로드 데이터 미리보기")
    st.dataframe(uploaded_df.head(20), width="stretch")

    suggested_mapping = infer_column_mapping(uploaded_df)
    st.markdown("#### 3. 컬럼 확인")
    st.caption("자동 추천값이 틀리면 source column을 직접 바꾸세요. Type이 없으면 기본 M으로 채워 예측하되 품질 경고를 남깁니다.")
    st.dataframe(suggested_mapping, width="stretch", hide_index=True)

    source_options = ["(not mapped)"] + uploaded_df.columns.astype(str).tolist()
    mapping: dict[str, str] = {}
    unit_conversions: dict[str, str] = {}
    mapping_columns = st.columns(2)
    for index, canonical in enumerate(CANONICAL_SENSOR_COLUMNS):
        default_source = suggested_mapping.loc[
            suggested_mapping["canonical_column"] == canonical,
            "suggested_source_column",
        ].iloc[0]
        default_index = source_options.index(default_source) if default_source in source_options else 0
        with mapping_columns[index % 2]:
            selected_source = st.selectbox(
                canonical,
                options=source_options,
                index=default_index,
                key=f"smart_mapping_{canonical}",
            )
            mapping[canonical] = "" if selected_source == "(not mapped)" else selected_source
            if canonical in NUMERIC_SENSOR_COLUMNS:
                unit_conversions[canonical] = st.selectbox(
                    f"{canonical} unit",
                    options=UNIT_OPTIONS,
                    index=0,
                    key=f"smart_unit_{canonical}",
                )

    policy_id = st.radio(
        "운영 정책",
        options=["balanced", "precision_first", "recall_first"],
        index=0,
        horizontal=True,
        format_func=lambda value: {
            "balanced": "균형 balanced",
            "precision_first": "오경보 감소 precision_first",
            "recall_first": "미탐 감소 recall_first",
        }[value],
        help="정책에 따라 High Risk threshold와 예상 alert trade-off가 달라집니다.",
    )

    st.markdown("#### 4. 예측 실행")
    if st.button("전처리와 예측 실행", type="primary", key="smart_predict_button"):
        try:
            with st.spinner("컬럼 매핑, 품질 진단, calibration 확률 예측을 실행하는 중입니다..."):
                result = predict_company_sensor_csv(
                    uploaded_df,
                    mapping=mapping,
                    unit_conversions=unit_conversions,
                    policy_id=policy_id,
                    write_outputs=True,
                )
            st.session_state["smart_csv_prediction_result"] = result
            record_audit(
                "smart_csv.predict",
                "success",
                "upload",
                getattr(uploaded_file, "name", "company_csv"),
                {
                    "row_count": int(len(result["result_df"])),
                    "quality_score": result["quality_report"]["quality_score"],
                    "policy_id": policy_id,
                    "high_risk_count": int((result["result_df"]["risk_status"] == "High Risk").sum()),
                },
            )
            st.success("전처리와 예측이 완료되었습니다.")
        except Exception as error:
            record_audit(
                "smart_csv.predict",
                "failure",
                "upload",
                getattr(uploaded_file, "name", "company_csv"),
                {"mapping": mapping, "unit_conversions": unit_conversions, "policy_id": policy_id},
                error_message=str(error),
            )
            st.error("전처리 또는 예측 중 문제가 발생했습니다.")
            st.warning("컬럼 매핑, 단위 선택, 숫자 형식, Type 값, 결측값을 확인하세요.")
            st.code(str(error), language="text")
            return

    result = st.session_state.get("smart_csv_prediction_result")
    if result is None:
        return

    result_df = result["result_df"]
    priority_df = result["priority_df"]
    quality_df = result["quality_df"]
    quality_report = result["quality_report"]
    policy = result["policy"]
    high_risk_count = int((result_df["risk_status"] == "High Risk").sum())
    max_probability = float(result_df["calibrated_probability"].max())

    st.markdown("#### 예측 요약")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("데이터 row", str(len(result_df)), "업로드 건수")
    with col2:
        metric_card("고위험 건수", str(high_risk_count), "선택 정책 기준")
    with col3:
        metric_card("최고 고장확률", f"{max_probability:.4f}", "보정 확률")
    with col4:
        metric_card("품질 점수", f"{quality_report['quality_score']:.1f}", quality_report["quality_status"])
    st.caption(f"운영 정책: {result['policy_id']} / 위험 판정 기준 {float(policy['threshold']):.2f}")

    st.markdown("#### 확률 그래프")
    chart_df = (
        result_df[["input_row", "raw_probability", "calibrated_probability"]]
        .rename(
            columns={
                "input_row": "입력 row",
                "raw_probability": "원 확률",
                "calibrated_probability": "보정 고장확률",
            }
        )
        .set_index("입력 row")
    )
    st.line_chart(chart_df, height=320)
    st.caption("원 확률은 모델의 기본 출력이고, 보정 고장확률은 기준 데이터에서 선택한 확률 보정을 적용한 값입니다.")

    st.markdown("#### 위험 우선순위")
    priority_columns = [
        "priority_rank",
        "input_row",
        "calibrated_probability",
        "risk_priority_score",
        "risk_status",
        "recommendation",
    ]
    priority_display = priority_df[priority_columns].head(30).rename(
        columns={
            "priority_rank": "우선순위",
            "input_row": "입력 row",
            "calibrated_probability": "보정 고장확률",
            "risk_priority_score": "우선순위 점수",
            "risk_status": "위험 상태",
            "recommendation": "추천 조치",
        }
    )
    st.dataframe(priority_display, width="stretch", hide_index=True)
    st.download_button(
        "위험 우선순위 CSV 다운로드",
        data=csv_download_bytes(priority_df),
        file_name="company_risk_priority_queue.csv",
        mime="text/csv",
    )

    with st.expander("데이터 품질 상세 보기"):
        quality_display = quality_df.rename(
            columns={
                "check": "점검 항목",
                "status": "상태",
                "detail": "상세",
                "affected_rows": "영향 row",
            }
        )
        st.dataframe(quality_display, width="stretch", hide_index=True)

    st.markdown("#### 예측 결과표와 다운로드")
    display_columns = [
        "input_row",
        "Type",
        "raw_probability",
        "calibrated_probability",
        "selected_threshold",
        "risk_status",
        "risk_priority_score",
        "data_quality_status",
        "recommendation",
    ]
    result_display = result_df.sort_values("calibrated_probability", ascending=False)[display_columns].rename(
        columns={
            "input_row": "입력 row",
            "raw_probability": "원 확률",
            "calibrated_probability": "보정 고장확률",
            "selected_threshold": "위험 기준",
            "risk_status": "위험 상태",
            "risk_priority_score": "우선순위 점수",
            "data_quality_status": "품질 상태",
            "recommendation": "추천 조치",
        }
    )
    st.dataframe(
        result_display,
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "예측 결과 CSV 다운로드",
        data=csv_download_bytes(result_df),
        file_name="company_prediction_results.csv",
        mime="text/csv",
    )

    policy_rows = []
    for policy_name in ["precision_first", "balanced", "recall_first"]:
        policy_row = result["policies"][policy_name]
        policy_rows.append(
            {
                "운영 정책": policy_name,
                "위험 판정 기준": round(float(policy_row["threshold"]), 2),
                "예상 정밀도": round(float(policy_row["precision"]), 4),
                "예상 재현율": round(float(policy_row["recall"]), 4),
                "예상 F1": round(float(policy_row["f1_score"]), 4),
                "예상 오경보": int(policy_row["false_alarm_count"]),
                "예상 미탐": int(policy_row["missed_failure_count"]),
            }
        )
    with st.expander("운영 정책별 위험 기준과 예상 trade-off"):
        st.dataframe(pd.DataFrame(policy_rows), width="stretch", hide_index=True)


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

    if REQUIRED_FILES["metrics"].exists():
        baseline_metrics = load_json(REQUIRED_FILES["metrics"])
        baseline_xgb = baseline_metrics["models"]["xgboost"]
        st.markdown("#### AI4I baseline 대비 재검증 요약")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "구분": "AI4I baseline",
                        "데이터": "public AI4I test split",
                        "PR-AUC": baseline_xgb["pr_auc"],
                        "F1-score": baseline_xgb["f1_score"],
                        "주의": "공개 데이터 기준 성능",
                    },
                    {
                        "구분": "업로드 CSV 재학습",
                        "데이터": "uploaded labeled company CSV",
                        "PR-AUC": xgboost_metrics["pr_auc"],
                        "F1-score": xgboost_metrics["f1_score"],
                        "주의": "업로드 데이터 split 기준 성능",
                    },
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.info(
            "실제 회사 데이터가 아닌 샘플 CSV로 실행한 경우, 이 결과는 재검증 기능 확인용입니다. "
            "실제 회사 데이터 성능 검증 완료라고 표현하지 않습니다."
        )

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
        record_audit(
            "company_retraining.save_outputs",
            "success",
            "directory",
            str(COMPANY_OUTPUT_DIR),
            {"artifact_count": len(saved_paths)},
        )
        st.success(f"저장 완료: {COMPANY_OUTPUT_DIR}")
        st.dataframe(
            pd.DataFrame(
                [{"artifact": key, "path": value} for key, value in saved_paths.items()]
            ),
            width="stretch",
            hide_index=True,
        )


def build_sample_labeled_company_dataframe() -> pd.DataFrame:
    """Create an AI4I-derived labeled company CSV for safe sample validation."""
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


def render_sample_company_revalidation() -> None:
    """Show the sample-company path separately from real company validation."""
    st.markdown("#### 샘플 데이터 재검증")
    st.caption(
        "AI4I를 회사형 컬럼명과 Celsius 단위로 바꾼 샘플입니다. "
        "기능 확인용이며 실제 회사 데이터 성능 검증으로 표현하지 않습니다."
    )
    sample_df = build_sample_labeled_company_dataframe()
    st.dataframe(sample_df.head(8), width="stretch", hide_index=True)
    sample_csv = sample_df.head(200).to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "샘플 labeled company CSV 다운로드",
        data=sample_csv,
        file_name="sample_labeled_company_csv.csv",
        mime="text/csv",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Rows", str(len(sample_df)), "AI4I-derived sample")
    with col2:
        metric_card("Target", "quality_result", "ok/failure")
    with col3:
        metric_card("Scope", "Sample", "not real company validation")

    if COMPANY_OUTPUT_DIR.exists():
        metrics_path = COMPANY_OUTPUT_DIR / "custom_metrics.json"
        threshold_path = COMPANY_OUTPUT_DIR / "custom_threshold_summary.json"
        predictions_path = COMPANY_OUTPUT_DIR / "custom_predictions.csv"
        if metrics_path.exists() and threshold_path.exists() and predictions_path.exists():
            metrics = load_json(metrics_path)
            threshold = load_json(threshold_path)
            predictions = pd.read_csv(predictions_path)
            xgb = metrics["models"]["xgboost"]
            st.markdown("##### 저장된 샘플 재검증 결과")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "dataset": "AI4I-derived sample company CSV",
                            "best_model": metrics["best_model_by_pr_auc"],
                            "xgboost_pr_auc": xgb["pr_auc"],
                            "xgboost_f1": xgb["f1_score"],
                            "selected_threshold": threshold["selected_threshold"],
                            "high_risk_rows": int((predictions["risk_status"] == "High Risk").sum()),
                            "claim_limit": "sample validation only",
                        }
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("샘플 재검증 산출물은 `src\\verify_company_generalization.py` 실행 후 표시됩니다.")
    else:
        st.info("샘플 재검증 산출물은 `src\\verify_company_generalization.py` 실행 후 표시됩니다.")


def render_company_retraining_tab() -> None:
    """Render sample and real labeled company CSV revalidation paths."""
    st.subheader("회사 CSV 재검증")
    st.caption(
        "샘플 데이터 검증과 실제 labeled company CSV 검증을 분리해서 표시합니다. "
        "라벨 없는 CSV는 데이터 예측 탭에서 예측/품질 진단만 수행합니다."
    )

    sample_tab, real_tab = st.tabs(["샘플 데이터 재검증", "실제 labeled company CSV 재검증"])
    with sample_tab:
        render_sample_company_revalidation()

    with real_tab:
        st.markdown("#### 실제 labeled company CSV 재검증")
        st.caption(
            "실제 회사 데이터로 성능을 말하려면 고장/정상 라벨, 설비 ID, timestamp, 센서 feature가 포함된 CSV가 필요합니다."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"구분": "필수", "항목": "target label", "설명": "고장/정상 또는 불량/정상 라벨"},
                    {"구분": "권장", "항목": "equipment/time", "설명": "설비 ID, timestamp, lot/batch 정보"},
                    {"구분": "필수", "항목": "sensor feature", "설명": "온도, 회전속도, 토크, 마모 등 숫자형 센서"},
                    {"구분": "선택", "항목": "unit conversion", "설명": "Celsius -> Kelvin 등 단위 표준화"},
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.warning(
            "실제 회사 CSV를 업로드해 재학습/평가한 경우에만 실제 회사 데이터 재검증 결과라고 표현합니다. "
            "라벨 없는 CSV는 성능 지표를 계산할 수 없습니다."
        )
        render_real_company_retraining_form()


def render_field_validation_evidence_tab() -> None:
    """Render field-validation report generation from company logs."""
    st.subheader("회사 데이터 실증")
    st.caption(
        "실제 회사 센서 라벨, 정비 이력, downtime/cost 로그가 있을 때만 실제 현장 성능과 비용 영향을 계산합니다. "
        "일부 파일만 있으면 가능한 지표와 불가능한 주장을 분리해서 표시합니다."
    )

    st.markdown("#### 입력 파일")
    col1, col2, col3 = st.columns(3)
    with col1:
        field_upload = st.file_uploader(
            "1. labeled sensor CSV",
            type=["csv"],
            key="field_validation_sensor_csv",
            help="equipment_id, timestamp, 센서값, actual_failure가 포함된 파일입니다.",
        )
    with col2:
        maintenance_upload = st.file_uploader(
            "2. 정비 이력 CSV",
            type=["csv"],
            key="field_validation_maintenance_csv",
            help="work_order_id, 정비 시작/종료, 조치 유형을 담은 파일입니다. 현재 리포트에는 추적성 참고 정보로 표시합니다.",
        )
    with col3:
        cost_upload = st.file_uploader(
            "3. downtime/cost CSV",
            type=["csv"],
            key="field_validation_cost_csv",
            help="downtime_minutes, parts_cost, labor_cost, lost_production_cost, baseline/new policy cost를 담은 파일입니다.",
        )

    template_col1, template_col2, template_col3, template_col4 = st.columns(4)
    with template_col1:
        if OPTIONAL_FILES["field_data_template"].exists():
            st.download_button(
                "센서 라벨 템플릿 다운로드",
                data=OPTIONAL_FILES["field_data_template"].read_bytes(),
                file_name="field_data_template.csv",
                mime="text/csv",
            )
    with template_col2:
        if OPTIONAL_FILES["field_maintenance_template"].exists():
            st.download_button(
                "정비 이력 템플릿 다운로드",
                data=OPTIONAL_FILES["field_maintenance_template"].read_bytes(),
                file_name="field_maintenance_template.csv",
                mime="text/csv",
            )
    with template_col3:
        if OPTIONAL_FILES["field_cost_template"].exists():
            st.download_button(
                "비용 로그 템플릿 다운로드",
                data=OPTIONAL_FILES["field_cost_template"].read_bytes(),
                file_name="field_cost_template.csv",
                mime="text/csv",
            )
    with template_col4:
        if OPTIONAL_FILES["field_validation_data_request_kit"].exists():
            st.download_button(
                "실증 데이터 요청 ZIP 다운로드",
                data=OPTIONAL_FILES["field_validation_data_request_kit"].read_bytes(),
                file_name="field_validation_data_request_kit.zip",
                mime="application/zip",
            )

    if field_upload is None:
        st.info("labeled sensor CSV를 업로드하면 성능 재평가 가능 여부를 확인합니다.")
        return

    if maintenance_upload is None:
        st.warning("정비 이력 CSV가 없으면 작업지시 추적성은 제한적으로만 해석합니다.")
    if cost_upload is None:
        st.warning("downtime/cost CSV가 없으면 실제 비용 절감 또는 downtime 감소를 주장할 수 없습니다.")

    if st.button("회사 데이터 실증 리포트 생성", type="primary"):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                field_path = temp_path / "field_data.csv"
                field_path.write_bytes(field_upload.getvalue())
                maintenance_path = None
                if maintenance_upload is not None:
                    maintenance_path = temp_path / "maintenance_history.csv"
                    maintenance_path.write_bytes(maintenance_upload.getvalue())
                cost_path = None
                if cost_upload is not None:
                    cost_path = temp_path / "field_cost.csv"
                    cost_path.write_bytes(cost_upload.getvalue())

                from evaluate_field_validation_report import evaluate_field_validation_package

                metrics = evaluate_field_validation_package(
                    field_path,
                    cost_path,
                    OUTPUT_DIR,
                    maintenance_data_path=maintenance_path,
                )

            st.success("회사 데이터 실증 리포트를 생성했습니다.")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                metric_card("Precision", str(metrics.get("precision")), "라벨 기준")
            with col2:
                metric_card("Recall", str(metrics.get("recall")), "라벨 기준")
            with col3:
                metric_card("Lead time", str(metrics.get("lead_time_minutes_mean")), "failure timestamp 필요")
            with col4:
                metric_card("Cost delta", str(metrics.get("maintenance_cost_delta_rate")), "before/after cost 필요")

            claim_status = str(metrics.get("claim_status", ""))
            if "cost" in claim_status and "not_supported" in claim_status:
                st.warning("현재 입력만으로 실제 비용 절감 또는 downtime 감소는 주장할 수 없습니다.")
            if claim_status == "field_validation_ready":
                st.info("before/after 비용 필드가 포함되어 비용 영향 계산까지 가능합니다. 실제 주장 전에는 기간과 설비군 조건을 함께 명시하세요.")
            if claim_status == "performance_and_traceability_only_cost_claim_not_supported":
                st.info("정비 이력까지 업로드되어 추적성 검토는 가능하지만, downtime/cost CSV가 없어 비용 영향은 주장할 수 없습니다.")

            report_path = Path(metrics["report_md"])
            st.markdown("#### 생성 리포트")
            st.markdown(report_path.read_text(encoding="utf-8"))
            st.markdown("#### 리포트 내보내기")
            export_columns = st.columns(4)
            export_files = [
                ("Markdown", Path(metrics["report_md"]), "field_validation_report.md", "text/markdown"),
                ("CSV", Path(metrics["report_csv"]), "field_validation_report.csv", "text/csv"),
                ("JSON", Path(metrics["report_json"]), "field_validation_report.json", "application/json"),
                ("ZIP", Path(metrics["report_zip"]), "field_validation_report_bundle.zip", "application/zip"),
            ]
            for column, (label, path, file_name, mime) in zip(export_columns, export_files):
                with column:
                    st.download_button(
                        f"{label} 다운로드",
                        data=path.read_bytes(),
                        file_name=file_name,
                        mime=mime,
                        key=f"field_validation_{file_name}",
                    )
        except Exception as error:
            st.error("회사 데이터 실증 리포트 생성에 실패했습니다.")
            st.exception(error)


def render_real_company_retraining_form() -> None:
    """Render the actual labeled company CSV retraining form."""
    uploaded_file = st.file_uploader(
        "실제 labeled company CSV 업로드",
        type=["csv"],
        key="company_retraining_csv",
        help="고장/불량 여부를 나타내는 target column이 포함된 CSV를 업로드합니다.",
    )

    if uploaded_file is None:
        st.info("실제 labeled company CSV를 업로드하면 이 화면에서 성능 재검증을 실행합니다.")
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
            record_audit(
                "company_retraining.run",
                "failure",
                "upload",
                getattr(uploaded_file, "name", "company_csv"),
                {
                    "target_column": target_column,
                    "id_time_columns": id_time_columns,
                },
                error_message=str(error),
            )
            st.error("회사 데이터 재학습 중 문제가 발생했습니다.")
            st.exception(error)
            return
        record_audit(
            "company_retraining.run",
            "success",
            "upload",
            getattr(uploaded_file, "name", "company_csv"),
            {
                "row_count": int(len(uploaded_df)),
                "target_column": target_column,
                "feature_count": len(feature_columns),
                "best_model": result["metrics"]["best_model_by_pr_auc"],
            },
        )

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
    st.subheader("위험 모니터링")
    st.caption(
        "저장된 센서 row 순서를 시간축처럼 재구성해 고장 확률 추세, 관리한계, 고위험 구간을 확인합니다."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Rows", str(spc_summary["total_rows"]), "monitoring records")
    with col2:
        metric_card("High Risk", str(spc_summary["high_risk_count"]), "threshold 이상")
    with col3:
        metric_card("SPC Alerts", str(spc_summary["spc_risk_alert_count"]), "risk limit or threshold")
    with col4:
        metric_card("Risk UCL", f"{spc_summary['risk_ucl']:.4f}", "3-sigma 관리한계")

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
            caption="Torque control chart as a model-linked process signal",
            width="stretch",
        )

    st.markdown(
        """
        <div class="callout">
        <strong>데이터 범위:</strong>
        이 화면은 운영망 실시간 스트림이 아니라 저장된 센서 row를 기반으로 위험 추세를 재구성합니다.
        실제 설비 적용 전에는 설비별 센서 주기, 단위, 결측 처리, 관리한계를 현장 데이터로 다시 확인해야 합니다.
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
    genai_settings: dict,
) -> None:
    """Render saved and optional live GenAI manager reports."""
    st.subheader("AI 리포트")
    st.caption(
        "고위험 또는 관리한계 이상 row를 선택해 관리자 참고 리포트를 생성합니다. "
        "API key는 왼쪽 사이드바에서 입력하며 파일에 저장하지 않습니다."
    )
    if genai_settings.get("has_key"):
        st.success(f"API 상태: {genai_status_text(genai_settings)}")
    else:
        st.warning("API key 없음: 저장된 기본 리포트를 표시하고 새 API 호출은 비활성화합니다.")

    candidate_rows = spc_timeseries[
        (spc_timeseries["risk_status"] == "High Risk") | spc_timeseries["spc_risk_alert"]
    ].copy()
    if candidate_rows.empty:
        candidate_rows = spc_timeseries.sort_values("xgboost_probability", ascending=False).head(20)
    else:
        candidate_rows = candidate_rows.sort_values("xgboost_probability", ascending=False)

    row_options = candidate_rows["time_step"].astype(int).tolist()
    selected_time_step = st.selectbox(
        "리포트 대상 센서 row",
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

    if st.button(
        "선택 row로 AI 리포트 생성",
        type="primary",
        disabled=not genai_settings.get("has_key"),
    ):
        try:
            report, mode = genai_report_with_sidebar_settings(context, genai_settings)
        except Exception as error:
            record_audit(
                "genai.report",
                "failure",
                "time_step",
                str(selected_time_step),
                {
                    "provider": genai_settings["provider"],
                    "model": genai_settings["model"],
                },
                error_message=str(error),
            )
            st.error(
                f"{genai_settings['provider_label']} API 호출에 실패했습니다. "
                f"model={genai_settings['model']}. API key는 표시하거나 저장하지 않았습니다."
            )
            st.code(str(error), language="text")
            return
        record_audit(
            "genai.report",
            "success",
            "time_step",
            str(selected_time_step),
            {
                "provider": genai_settings["provider"],
                "model": genai_settings["model"],
                "mode": mode,
            },
        )
        st.success(f"리포트 생성 모드: {mode}")
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


def initialize_stage19_form_defaults() -> None:
    """Set product-style default values for the field-event form."""
    normal_row = STAGE19_SENSOR_PRESETS["Normal 샘플"]
    defaults = {
        "stage19_equipment_id": "press-01",
        "stage19_event_timestamp": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "stage19_source_system": "streamlit_dashboard",
        "stage19_type": normal_row["Type"],
        "stage19_air_temp": float(normal_row["Air temperature [K]"]),
        "stage19_process_temp": float(normal_row["Process temperature [K]"]),
        "stage19_rotational_speed": int(normal_row["Rotational speed [rpm]"]),
        "stage19_torque": float(normal_row["Torque [Nm]"]),
        "stage19_tool_wear": int(normal_row["Tool wear [min]"]),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def apply_stage19_preset(preset_name: str) -> None:
    """Apply one sensor preset to the field-event form."""
    row = STAGE19_SENSOR_PRESETS[preset_name]
    st.session_state["stage19_type"] = row["Type"]
    st.session_state["stage19_air_temp"] = float(row["Air temperature [K]"])
    st.session_state["stage19_process_temp"] = float(row["Process temperature [K]"])
    st.session_state["stage19_rotational_speed"] = int(row["Rotational speed [rpm]"])
    st.session_state["stage19_torque"] = float(row["Torque [Nm]"])
    st.session_state["stage19_tool_wear"] = int(row["Tool wear [min]"])


def render_stage19_20_input_controls(events: list[dict], drafts: list[dict]) -> None:
    """Render sensor event and work-order decision controls."""
    initialize_stage19_form_defaults()
    last_message = st.session_state.pop("operations_last_message", None)
    if last_message:
        st.success(last_message)

    st.markdown("#### 센서 row 입력")
    st.caption(
        "단일 설비의 센서 값을 입력하면 로컬 예측 함수가 고장 확률과 High Risk 여부를 계산하고, "
        "센서 이벤트, 작업지시 초안, 승인/검토/반려 기록을 SQLite와 CSV export에 저장합니다."
    )

    with st.expander("센서 row 입력 및 이벤트 생성", expanded=True):
        st.markdown("단일 설비 센서 row를 직접 입력하거나 아래 프리셋으로 빠르게 채울 수 있습니다.")
        preset_col1, preset_col2 = st.columns(2)
        with preset_col1:
            if st.button("Normal 샘플 채우기", key="stage19_normal_preset"):
                apply_stage19_preset("Normal 샘플")
                st.rerun()
        with preset_col2:
            if st.button("High Risk 샘플 채우기", key="stage19_high_risk_preset"):
                apply_stage19_preset("High Risk 샘플")
                st.rerun()

        with st.form("stage19_field_event_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                equipment_id = st.text_input("설비 ID", key="stage19_equipment_id")
            with col2:
                event_timestamp = st.text_input(
                    "이벤트 시각",
                    key="stage19_event_timestamp",
                )
            with col3:
                source_system = st.text_input("입력 출처", key="stage19_source_system")

            col1, col2, col3 = st.columns(3)
            with col1:
                type_value = st.selectbox("제품 등급", options=["L", "M", "H"], key="stage19_type")
                air_temp = st.number_input("공기 온도 [K]", step=0.1, key="stage19_air_temp")
            with col2:
                process_temp = st.number_input(
                    "공정 온도 [K]",
                    step=0.1,
                    key="stage19_process_temp",
                )
                rotational_speed = st.number_input(
                    "회전 속도 [rpm]",
                    step=1,
                    key="stage19_rotational_speed",
                )
            with col3:
                torque = st.number_input("토크 [Nm]", step=0.1, key="stage19_torque")
                tool_wear = st.number_input("공구 마모 [min]", step=1, key="stage19_tool_wear")

            submitted = st.form_submit_button("센서 이벤트 생성", type="primary")

        if submitted:
            row = {
                "Type": type_value,
                "Air temperature [K]": float(air_temp),
                "Process temperature [K]": float(process_temp),
                "Rotational speed [rpm]": int(rotational_speed),
                "Torque [Nm]": float(torque),
                "Tool wear [min]": int(tool_wear),
            }
            try:
                event = predict_field_event(
                    equipment_id=equipment_id,
                    event_timestamp=event_timestamp,
                    source_system=source_system,
                    row=row,
                    persist=True,
                    db_path=OPERATIONS_DB_PATH,
                )
            except Exception as error:
                record_audit(
                    "field_event.create",
                    "failure",
                    "equipment",
                    equipment_id,
                    {"source_system": source_system},
                    error_message=str(error),
                )
                st.error("센서 이벤트 생성 중 문제가 발생했습니다.")
                st.exception(error)
            else:
                record_audit(
                    "field_event.create",
                    "success",
                    "event",
                    event["event_id"],
                    {
                        "equipment_id": equipment_id,
                        "source_system": source_system,
                        "risk_status": event["risk_status"],
                        "probability": event["probability"],
                    },
                )
                st.session_state["operations_last_message"] = (
                    f"센서 이벤트 생성 완료: {event['event_id'][:8]} / {event['risk_status']}"
                )
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 작업지시 초안 생성")
        if not events:
            st.info("먼저 센서 이벤트 또는 예측 기록을 생성하세요.")
        else:
            event_map = {event["event_id"]: event for event in events}
            selected_event_id = st.selectbox(
                "초안을 만들 센서 이벤트",
                options=list(event_map),
                format_func=lambda event_id: (
                    f"{event_map[event_id]['risk_status']} / "
                    f"{event_map[event_id]['probability']:.4f} / {event_id[:8]}"
                ),
                key="stage20_draft_event_select",
            )
            if st.button("작업지시 초안 생성", key="create_stage20_draft"):
                try:
                    draft = create_work_order_draft(
                        event_map[selected_event_id],
                        db_path=OPERATIONS_DB_PATH,
                    )
                except Exception as error:
                    record_audit(
                        "work_order_draft.create",
                        "failure",
                        "event",
                        selected_event_id,
                        error_message=str(error),
                    )
                    st.error("작업지시 초안 생성 중 문제가 발생했습니다.")
                    st.exception(error)
                else:
                    record_audit(
                        "work_order_draft.create",
                        "success",
                        "draft",
                        draft["draft_id"],
                        {"event_id": draft["event_id"]},
                    )
                    st.session_state["operations_last_message"] = (
                        f"작업지시 초안 생성 완료: {draft['draft_id'][:8]}"
                    )
                    st.rerun()

    with col2:
        st.markdown("#### 승인/검토/반려 결정")
        if not drafts:
            st.info("먼저 작업지시 초안을 생성하세요.")
        else:
            draft_map = {draft["draft_id"]: draft for draft in drafts}
            selected_draft_id = st.selectbox(
                "결정할 작업지시 초안",
                options=list(draft_map),
                format_func=lambda draft_id: (
                    f"{draft_map[draft_id]['created_at']} / {draft_id[:8]}"
                ),
                key="stage20_decision_draft_select",
            )
            decision = st.radio(
                "결정",
                options=["approve", "needs_review", "reject"],
                horizontal=True,
                key="stage20_decision_radio",
                format_func=lambda value: {
                    "approve": "승인 (approve)",
                    "needs_review": "검토 필요 (needs_review)",
                    "reject": "반려 (reject)",
                }[value],
            )
            operator_id = st.text_input(
                "작업자 ID",
                value=current_actor().get("actor_id", "operator_01"),
                key="stage20_operator_id",
            )
            note = st.text_area(
                "메모",
                value="대시보드에서 검토했습니다.",
                key="stage20_decision_note",
            )
            if st.button("결정 기록 저장", key="save_stage20_decision"):
                try:
                    saved = create_work_order_decision(
                        draft_id=selected_draft_id,
                        decision=decision,
                        operator_id=operator_id,
                        note=note,
                        db_path=OPERATIONS_DB_PATH,
                    )
                except Exception as error:
                    record_audit(
                        "work_order_decision.create",
                        "failure",
                        "draft",
                        selected_draft_id,
                        {"decision": decision, "operator_id": operator_id},
                        error_message=str(error),
                    )
                    st.error("결정 기록 중 문제가 발생했습니다.")
                    st.exception(error)
                else:
                    record_audit(
                        "work_order_decision.create",
                        "success",
                        "decision",
                        saved["decision_id"],
                        {
                            "draft_id": selected_draft_id,
                            "event_id": saved["event_id"],
                            "decision": saved["decision"],
                            "operator_id": operator_id,
                            "retraining_candidate": saved["decision"] == "needs_review",
                        },
                    )
                    st.session_state["operations_last_message"] = (
                        f"결정 저장 완료: {saved['decision_id'][:8]} / {saved['decision']}"
                    )
                    st.rerun()


def render_stage15_20_operations_tab(ai_context: dict) -> None:
    """Render local API, SQLite event history, and work-order decision status."""
    st.subheader("승인형 작업지시 운영 PoC")
    st.caption(
        "센서 row 입력부터 event 생성, 작업지시 초안, 작업자 승인/검토/반려 기록까지 한 흐름으로 확인합니다."
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

    render_stage19_20_input_controls(events, drafts)

    with st.expander("개발/검증 실행 명령 보기"):
        st.code(
            ".\\run_stage1_20_gemini.ps1\n"
            "# OpenAI 경로를 쓰려면 .\\run_stage1_20_openai.ps1\n"
            ".\\.venv\\Scripts\\python.exe -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000\n"
            ".\\.venv\\Scripts\\python.exe src\\verify_stage19_20_integration.py",
            language="powershell",
        )

    st.markdown("#### 최근 기록: 예측 이벤트")
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

    st.markdown("#### 최근 기록: 작업지시 초안")
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

    st.markdown("#### 최근 기록: operator decision")
    if decisions:
        action_labels = {
            "approve": "승인됨: 작업자가 현장 점검을 허용",
            "reject": "반려됨: 초안은 실행하지 않음",
            "needs_review": "보류됨: 관리자 검토 및 재학습 후보",
        }
        decision_rows = [
            {
                "created_at": decision["created_at"],
                "decision_id": decision["decision_id"],
                "draft_id": decision["draft_id"],
                "event_id": decision["event_id"],
                "operator_id": decision["operator_id"],
                "decision": decision["decision"],
                "action_history": action_labels.get(decision["decision"], "기록됨"),
                "retraining_candidate": decision["decision"] == "needs_review",
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
        st.info("아직 operator decision 기록이 없습니다.")

    mock_summary = load_optional_markdown(OPTIONAL_FILES["mock_bridge_summary"])
    if mock_summary:
        with st.expander("MQTT/OPC UA local mock bridge 실행 요약"):
            st.markdown(mock_summary)

    if STAGE15_20_ARCHITECTURE_PATH.exists():
        with st.expander("상세 아키텍처 문서 보기"):
            st.markdown(STAGE15_20_ARCHITECTURE_PATH.read_text(encoding="utf-8"))
    else:
        st.info("`src\\verify_stage19_20_integration.py` 실행 후 문서가 생성됩니다.")


def render_markdown_tab(title: str, markdown_text: str) -> None:
    """Render a Markdown output file inside a tab."""
    st.subheader(title)
    st.markdown(markdown_text)


def render_comparison_evidence() -> None:
    """Show optional comparison artifacts without blocking the dashboard."""
    model_summary = load_optional_markdown(OPTIONAL_FILES["model_strategy_summary"])
    spc_summary = load_optional_markdown(OPTIONAL_FILES["spc_vs_ml_summary"])

    if not model_summary and not spc_summary:
        st.info(
            "비교 실험 산출물이 아직 없습니다. "
            "`src\\compare_model_strategies.py`와 `src\\compare_spc_ml_alerts.py`를 실행하면 여기에 표시됩니다."
        )
        return

    st.markdown("#### 비교 실험 근거")
    if OPTIONAL_FILES["model_strategy_comparison"].exists():
        strategy_df = pd.read_csv(OPTIONAL_FILES["model_strategy_comparison"])
        display_columns = [
            "display_name",
            "threshold",
            "precision",
            "recall",
            "f1_score",
            "pr_auc",
            "alert_count",
            "false_positive",
            "false_negative",
        ]
        st.dataframe(strategy_df[display_columns], width="stretch", hide_index=True)
    if OPTIONAL_FILES["model_strategy_pr_curve"].exists():
        st.image(
            str(OPTIONAL_FILES["model_strategy_pr_curve"]),
            caption="Model strategy PR curve comparison",
            width="stretch",
        )
    if model_summary:
        with st.expander("SMOTE / threshold 비교 요약"):
            st.markdown(model_summary)

    if OPTIONAL_FILES["spc_vs_ml_comparison"].exists():
        spc_df = pd.read_csv(OPTIONAL_FILES["spc_vs_ml_comparison"])
        display_columns = [
            "display_name",
            "precision",
            "recall",
            "f1_score",
            "alert_count",
            "false_positive",
            "false_negative",
        ]
        st.dataframe(spc_df[display_columns], width="stretch", hide_index=True)
    if spc_summary:
        with st.expander("SPC-only vs ML+SPC 비교 요약"):
            st.markdown(spc_summary)


def render_industrial_engineering_evidence_tab() -> None:
    """Show industrial-engineering theory links and generated evidence."""
    st.subheader("산업공학 검증 근거")
    st.caption(
        "OEE/MTBF/MTTR, FMEA/RPN, SPC 관리한계, cost simulation, risk priority score를 논문용으로 연결합니다."
    )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "개념": "OEE",
                    "수식": "OEE = Availability x Performance x Quality",
                    "시스템 연결": "고위험 alert와 작업지시 이력을 Availability 관리 후보 지표로 연결",
                    "주의": "AI4I만으로 실제 OEE 개선을 증명하지 않음",
                },
                {
                    "개념": "MTBF",
                    "수식": "MTBF = total operating time / number of failures",
                    "시스템 연결": "고장 이력과 운영시간 로그가 있으면 신뢰성 지표로 확장 가능",
                    "주의": "현장 운영시간 로그 없이는 개선 주장 불가",
                },
                {
                    "개념": "MTTR",
                    "수식": "MTTR = total repair time / number of repairs",
                    "시스템 연결": "작업지시 승인/조치 이력과 수리시간 로그를 연결 가능",
                    "주의": "수리시간 실측 없이는 단축 주장 불가",
                },
                {
                    "개념": "FMEA/RPN",
                    "수식": "RPN = Severity x Occurrence x Detection",
                    "시스템 연결": "risk_priority_score를 FMEA-inspired priority로 설명",
                    "주의": "공식 FMEA sheet 대체 아님",
                },
                {
                    "개념": "SPC",
                    "수식": "UCL/LCL = mean +/- 3 x sigma",
                    "시스템 연결": "고장확률/센서 추세를 관리도 문맥으로 표시",
                    "주의": "설비별 정상기간 데이터로 관리한계 재설정 필요",
                },
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### Risk priority score")
    st.code(
        "risk_priority_score = clip(\n"
        "    72 * calibrated_probability\n"
        "  + 14 * I(calibrated_probability >= policy_threshold)\n"
        "  + 0.14 * (100 - quality_score)\n"
        "  + 10 * clip(missed_failure_weight / max(false_alarm_weight, 0.1), 0, 30) / 30,\n"
        "  0,\n"
        "  100\n"
        ")",
        language="text",
    )

    if OPTIONAL_FILES["operating_policy_thresholds"].exists():
        policy_payload = load_json(OPTIONAL_FILES["operating_policy_thresholds"])
        policy_rows = [
            {"policy": policy_id, **policy}
            for policy_id, policy in policy_payload.get("policies", {}).items()
        ]
        if policy_rows:
            st.markdown("#### 운영 정책 threshold")
            st.dataframe(pd.DataFrame(policy_rows), width="stretch", hide_index=True)

    if OPTIONAL_FILES["operational_value_comparison"].exists():
        value_df = pd.read_csv(OPTIONAL_FILES["operational_value_comparison"])
        st.markdown("#### Cost simulation")
        st.dataframe(
            value_df[
                [
                    "scenario_id",
                    "policy_id",
                    "alert_count",
                    "false_alarm_count",
                    "missed_failure_count",
                    "normalized_operating_cost",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    evidence_text = load_optional_markdown(OPTIONAL_FILES["industrial_engineering_evidence"])
    if evidence_text:
        st.markdown("#### 논문용 산업공학 근거 문서")
        st.markdown(evidence_text)
        st.download_button(
            "industrial_engineering_evidence.md 다운로드",
            data=evidence_text.encode("utf-8"),
            file_name="industrial_engineering_evidence.md",
            mime="text/markdown",
        )
    else:
        st.info("`src\\create_industrial_engineering_evidence.py` 실행 후 근거 문서가 표시됩니다.")


def render_open_industrial_validation_tab() -> None:
    """Show optional open industrial dataset validation artifacts."""
    st.subheader("공개 산업 데이터 검증")
    st.caption(
        "SCANIA Component X 같은 공개 산업 데이터셋을 연결해 실제 산업 데이터에 가까운 benchmark를 수행하는 화면입니다."
    )

    st.info(
        "원본 공개 데이터는 용량과 라이선스 때문에 GitHub에 포함하지 않습니다. "
        "`data_external/scania_component_x/`에 파일을 넣고 `src\\open_industrial_validation.py`를 실행하면 실제 공개 데이터 경로로 검증합니다."
    )

    public_metrics_path = OPTIONAL_FILES["public_industrial_validation_metrics"]
    public_cost_path = OPTIONAL_FILES["public_industrial_cost_simulation"]
    public_rul_path = OPTIONAL_FILES["public_industrial_rul_metrics"]
    public_report = load_optional_markdown(OPTIONAL_FILES["public_industrial_validation_report"])
    public_claims = load_optional_markdown(OPTIONAL_FILES["public_benchmark_claims"])
    if public_metrics_path.exists():
        public_df = pd.read_csv(public_metrics_path)
        dataset_count = public_df["dataset_id"].nunique()
        best_rows = (
            public_df.sort_values(["dataset_id", "f1_score", "recall"], ascending=[True, False, False])
            .groupby("dataset_id", as_index=False)
            .head(1)
        )
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_card("Datasets", str(dataset_count), "MetroPT/C-MAPSS/IMS/FEMTO")
        with col2:
            metric_card("Best Avg F1", f"{best_rows['f1_score'].mean():.4f}", "best per dataset")
        with col3:
            metric_card("Best Avg Recall", f"{best_rows['recall'].mean():.4f}", "best per dataset")
        with col4:
            metric_card("Avg Lead Time", f"{best_rows['mean_lead_time_steps'].mean():.2f}", "steps")

        st.markdown("#### Public benchmark adapter summary")
        st.dataframe(
            best_rows[
                [
                    "dataset_id",
                    "source_mode",
                    "label_scope",
                    "display_name",
                    "precision",
                    "recall",
                    "f1_score",
                    "pr_auc",
                    "early_warning_rate",
                    "mean_lead_time_steps",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        chart_cols = st.columns(3)
        chart_specs = [
            ("public_industrial_lead_time_chart", "Public benchmark lead-time summary"),
            ("public_industrial_cost_chart", "Public benchmark simulated cost summary"),
            ("public_industrial_rul_chart", "Public benchmark RUL error summary"),
        ]
        for column, (file_key, caption) in zip(chart_cols, chart_specs):
            with column:
                if OPTIONAL_FILES[file_key].exists():
                    st.image(str(OPTIONAL_FILES[file_key]), caption=caption, width="stretch")

        if public_cost_path.exists():
            public_cost_df = pd.read_csv(public_cost_path)
            st.markdown("#### Public benchmark simulated cost")
            st.dataframe(
                public_cost_df[
                    [
                        "dataset_id",
                        "scenario_id",
                        "display_name",
                        "normalized_operating_cost",
                        "simulated_cost_delta_vs_no_alert",
                        "cost_scope",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

        if public_rul_path.exists():
            public_rul_df = pd.read_csv(public_rul_path)
            st.markdown("#### RUL benchmark metrics")
            st.dataframe(
                public_rul_df[
                    [
                        "dataset_id",
                        "source_mode",
                        "display_name",
                        "rmse",
                        "mae",
                        "nasa_style_rul_score",
                        "rul_scope",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

        if OPTIONAL_FILES["public_industrial_confusion_matrix"].exists():
            st.image(
                str(OPTIONAL_FILES["public_industrial_confusion_matrix"]),
                caption="Representative public benchmark confusion matrix",
                width="stretch",
            )

        if public_report:
            with st.expander("Public industrial benchmark report"):
                st.markdown(public_report)
        if public_claims:
            with st.expander("Public benchmark claims and guardrails"):
                st.markdown(public_claims)
    else:
        st.info("Public benchmark summary is shown after running `src\\public_industrial_benchmark.py`.")

    official_metrics_path = OPTIONAL_FILES["scania_official_cost_metrics"]
    official_report = load_optional_markdown(OPTIONAL_FILES["scania_official_cost_report"])
    if official_metrics_path.exists():
        official_df = pd.read_csv(official_metrics_path)
        best_cost = official_df.sort_values("official_cost", ascending=True).iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_card("Best Official Cost", f"{best_cost['official_cost']:.0f}", best_cost["strategy_id"])
        with col2:
            metric_card(
                "Rule 대비 개선",
                f"{float(best_cost['cost_improvement_vs_rule']) * 100:.2f}%",
                "official cost metric",
            )
        with col3:
            metric_card(
                "No-alert 대비 개선",
                f"{float(best_cost['cost_improvement_vs_no_alert']) * 100:.2f}%",
                "official cost metric",
            )
        with col4:
            metric_card(
                "Alert-like Rate",
                f"{float(best_cost['alert_like_rate']) * 100:.2f}%",
                "점검/경보 부담",
            )

        st.markdown("#### SCANIA official class 0~4 cost metric")
        official_columns = [
            "strategy_id",
            "official_cost",
            "normalized_cost",
            "cost_improvement_vs_rule",
            "cost_improvement_vs_no_alert",
            "alert_like_rate",
            "macro_f1",
            "balanced_accuracy",
            "recall_class_0",
            "recall_class_4",
        ]
        st.dataframe(official_df[official_columns], width="stretch", hide_index=True)
        st.warning(
            "이 수치는 SCANIA 공개 benchmark의 official cost metric 개선율입니다. "
            "실제 사업장 원화 비용 절감이나 탐지 시간 단축 실증은 별도 현장 로그가 필요합니다."
        )
    else:
        st.info("SCANIA official class 0~4 cost metric 산출물은 `src\\scania_official_cost_validation.py` 실행 후 표시됩니다.")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        if OPTIONAL_FILES["scania_official_cost_chart"].exists():
            st.image(
                str(OPTIONAL_FILES["scania_official_cost_chart"]),
                caption="SCANIA official cost comparison",
                width="stretch",
            )
    with chart_col2:
        if OPTIONAL_FILES["scania_official_confusion_matrix"].exists():
            st.image(
                str(OPTIONAL_FILES["scania_official_confusion_matrix"]),
                caption="Best official-cost strategy confusion matrix",
                width="stretch",
            )
    if official_report:
        with st.expander("SCANIA official cost metric 리포트"):
            st.markdown(official_report)

    render_field_validation_workbench()

    field_protocol = load_optional_markdown(OPTIONAL_FILES["field_validation_protocol"])
    if field_protocol:
        with st.expander("실제 현장 실증 프로토콜과 템플릿"):
            st.info(
                "실제 비용 절감률이나 탐지 시간 단축률을 주장하려면 센서값뿐 아니라 "
                "고장 라벨, 정비 시작/종료, downtime, 부품비, 인건비 로그가 함께 필요합니다."
            )
            field_cols = st.columns(4)
            with field_cols[0]:
                metric_card("필수 데이터", "센서 + 고장 라벨", "설비 ID와 timestamp 포함")
            with field_cols[1]:
                metric_card("필수 이력", "정비 시작/종료", "lead time 계산")
            with field_cols[2]:
                metric_card("필수 비용", "부품비 + 인건비", "cost simulation 보정")
            with field_cols[3]:
                metric_card("주장 범위", "before/after 비교", "현장 로그 있을 때만")
            st.markdown(field_protocol)
            col1, col2 = st.columns(2)
            with col1:
                if OPTIONAL_FILES["field_data_template"].exists():
                    st.caption("센서/고장 라벨 템플릿 미리보기")
                    st.dataframe(
                        pd.read_csv(OPTIONAL_FILES["field_data_template"]).head(5),
                        width="stretch",
                        hide_index=True,
                    )
                    st.download_button(
                        "현장 센서/고장 라벨 템플릿 다운로드",
                        data=OPTIONAL_FILES["field_data_template"].read_bytes(),
                        file_name="field_data_template.csv",
                        mime="text/csv",
                    )
            with col2:
                if OPTIONAL_FILES["field_cost_template"].exists():
                    st.caption("정비 비용 로그 템플릿 미리보기")
                    st.dataframe(
                        pd.read_csv(OPTIONAL_FILES["field_cost_template"]).head(5),
                        width="stretch",
                        hide_index=True,
                    )
                    st.download_button(
                        "현장 비용 로그 템플릿 다운로드",
                        data=OPTIONAL_FILES["field_cost_template"].read_bytes(),
                        file_name="field_cost_template.csv",
                        mime="text/csv",
                    )

    metrics_path = OPTIONAL_FILES["open_industrial_validation_metrics"]
    cost_path = OPTIONAL_FILES["open_industrial_cost_simulation"]
    report_text = load_optional_markdown(OPTIONAL_FILES["open_industrial_validation_report"])
    lead_text = load_optional_markdown(OPTIONAL_FILES["open_industrial_lead_time_report"])

    if metrics_path.exists():
        metrics_df = pd.read_csv(metrics_path)
        source_mode = str(metrics_df["source_mode"].iloc[0]) if "source_mode" in metrics_df else "unknown"
        best_f1 = metrics_df.sort_values(["f1_score", "recall"], ascending=[False, False]).iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_card("Source", source_mode, "sample or public data")
        with col2:
            metric_card("Best F1", f"{best_f1['f1_score']:.4f}", best_f1["display_name"])
        with col3:
            metric_card("Recall", f"{best_f1['recall']:.4f}", "best F1 strategy")
        with col4:
            metric_card("PR-AUC", f"{best_f1['pr_auc']:.4f}", "best F1 strategy")

        display_columns = [
            "display_name",
            "precision",
            "recall",
            "f1_score",
            "pr_auc",
            "alert_count",
            "false_alarm_count",
            "missed_failure_count",
            "early_warning_rate",
            "mean_lead_time_steps",
        ]
        st.markdown("#### 공개 산업 데이터 비교군 성능")
        st.dataframe(metrics_df[display_columns], width="stretch", hide_index=True)
    else:
        st.warning("공개 산업 데이터 검증 산출물이 아직 없습니다. `src\\open_industrial_validation.py`를 실행하세요.")

    if OPTIONAL_FILES["open_industrial_lead_time_chart"].exists():
        st.image(
            str(OPTIONAL_FILES["open_industrial_lead_time_chart"]),
            caption="Open industrial validation lead-time comparison",
            width="stretch",
        )

    if cost_path.exists():
        cost_df = pd.read_csv(cost_path)
        st.markdown("#### 공개 산업 데이터 cost simulation")
        st.dataframe(
            cost_df[
                [
                    "strategy_id",
                    "operating_cost_units",
                    "normalized_operating_cost",
                    "simulated_cost_delta_vs_no_alert",
                    "cost_scope",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    if report_text:
        with st.expander("Open industrial validation report"):
            st.markdown(report_text)
    if lead_text:
        with st.expander("Lead-time report"):
            st.markdown(lead_text)


def render_field_validation_workbench() -> None:
    """Generate a company field-validation report from uploaded labeled logs."""
    st.markdown("### 실제 회사 데이터 실증 리포트")
    st.caption(
        "센서/고장 라벨 CSV와 정비 비용 로그 CSV를 함께 넣으면 precision, recall, false alarm, missed failure, "
        "lead time, downtime, cost delta를 계산합니다. 업로드 원본은 저장하지 않고 결과 리포트만 저장합니다."
    )

    top_cols = st.columns(4)
    with top_cols[0]:
        metric_card("입력 1", "센서 + 고장 라벨", "actual_failure 필수")
    with top_cols[1]:
        metric_card("입력 2", "정비 비용 로그", "downtime/cost 필수")
    with top_cols[2]:
        metric_card("출력", "실증 리포트", "CSV/JSON/MD")
    with top_cols[3]:
        metric_card("주장", "로그 있을 때만", "실제 절감률 분리")

    st.info(
        "`baseline_total_cost`와 `new_policy_total_cost`가 비용 로그에 있으면 cost delta를 계산합니다. "
        "해당 컬럼이 없으면 비용 절감 실증이 아니라 예측/추적성 리포트로만 표시합니다."
    )

    demo_col, upload_col = st.columns([1, 2])
    with demo_col:
        st.markdown("#### 템플릿 샘플 실행")
        st.write("템플릿으로 리포트 생성 기능만 확인합니다. 실제 회사 데이터 실증으로 표현하지 않습니다.")
        if st.button("템플릿 샘플 리포트 생성", type="secondary"):
            try:
                from evaluate_field_validation_report import evaluate_field_validation

                metrics = evaluate_field_validation(
                    OPTIONAL_FILES["field_data_template"],
                    OPTIONAL_FILES["field_cost_template"],
                    OUTPUT_DIR,
                    source_mode_override="template_demo",
                )
                record_audit(
                    "field_validation.sample_report",
                    "success",
                    "field_validation",
                    "template_demo",
                    {"claim_status": metrics.get("claim_status")},
                )
                st.success("템플릿 샘플 리포트를 생성했습니다.")
                st.rerun()
            except Exception as error:
                record_audit(
                    "field_validation.sample_report",
                    "error",
                    "field_validation",
                    "template_demo",
                    error_message=str(error),
                )
                st.error(f"템플릿 샘플 리포트 생성 실패: {error}")

    with upload_col:
        st.markdown("#### 실제 labeled company CSV + 비용 로그")
        field_upload = st.file_uploader(
            "센서/고장 라벨 CSV 업로드",
            type=["csv"],
            key="field_validation_field_upload",
            help="equipment_id, timestamp, 센서값, actual_failure, 선택적으로 failure_timestamp가 필요합니다.",
        )
        cost_upload = st.file_uploader(
            "정비 비용 로그 CSV 업로드",
            type=["csv"],
            key="field_validation_cost_upload",
            help="work_order_id, downtime_minutes, parts_cost, labor_cost, lost_production_cost 등이 필요합니다.",
        )
        if field_upload and cost_upload:
            preview_cols = st.columns(2)
            with preview_cols[0]:
                st.caption("센서/고장 라벨 미리보기")
                try:
                    st.dataframe(pd.read_csv(field_upload).head(5), width="stretch", hide_index=True)
                    field_upload.seek(0)
                except Exception as error:
                    st.error(f"센서 CSV 미리보기 실패: {error}")
            with preview_cols[1]:
                st.caption("정비 비용 로그 미리보기")
                try:
                    st.dataframe(pd.read_csv(cost_upload).head(5), width="stretch", hide_index=True)
                    cost_upload.seek(0)
                except Exception as error:
                    st.error(f"비용 CSV 미리보기 실패: {error}")

            if st.button("실제 회사 로그로 실증 리포트 생성", type="primary"):
                try:
                    from evaluate_field_validation_report import evaluate_field_validation

                    with tempfile.TemporaryDirectory() as tmp_dir:
                        tmp_path = Path(tmp_dir)
                        field_path = tmp_path / "field_data.csv"
                        cost_path = tmp_path / "field_cost.csv"
                        field_path.write_bytes(field_upload.getvalue())
                        cost_path.write_bytes(cost_upload.getvalue())
                        metrics = evaluate_field_validation(
                            field_path,
                            cost_path,
                            OUTPUT_DIR,
                            source_mode_override="company_field_logs",
                        )
                    record_audit(
                        "field_validation.company_report",
                        "success",
                        "field_validation",
                        "company_field_logs",
                        {
                            "field_data_rows": metrics.get("field_data_rows"),
                            "cost_rows": metrics.get("cost_rows"),
                            "claim_status": metrics.get("claim_status"),
                        },
                    )
                    st.success("실제 회사 로그 기반 실증 리포트를 생성했습니다. 원본 업로드 파일은 저장하지 않았습니다.")
                    st.rerun()
                except Exception as error:
                    record_audit(
                        "field_validation.company_report",
                        "error",
                        "field_validation",
                        "company_field_logs",
                        error_message=str(error),
                    )
                    st.error(f"실증 리포트 생성 실패: {error}")
        else:
            st.warning("두 CSV를 모두 업로드해야 실제 회사 로그 기반 리포트를 생성할 수 있습니다.")

    report_path = OPTIONAL_FILES["field_validation_report"]
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    report_json_path = OPTIONAL_FILES["field_validation_report_json"]
    if report_text:
        st.divider()
        st.markdown("#### 최근 생성된 실증 리포트")
        if report_json_path.exists():
            try:
                report_meta = json.loads(report_json_path.read_text(encoding="utf-8"))
                cols = st.columns(4)
                with cols[0]:
                    metric_card("source_mode", str(report_meta.get("source_mode")), "template or company logs")
                with cols[1]:
                    metric_card("claim_status", str(report_meta.get("claim_status")), "claim guardrail")
                with cols[2]:
                    metric_card("recall", str(report_meta.get("recall")), "failure capture")
                with cols[3]:
                    metric_card("cost_delta", str(report_meta.get("maintenance_cost_delta_rate")), "direct cost fields only")
            except Exception:
                pass
        if OPTIONAL_FILES["field_validation_report_csv"].exists():
            st.dataframe(
                pd.read_csv(OPTIONAL_FILES["field_validation_report_csv"]),
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "실증 리포트 CSV 다운로드",
                data=OPTIONAL_FILES["field_validation_report_csv"].read_bytes(),
                file_name="field_validation_report.csv",
                mime="text/csv",
            )
        st.download_button(
            "실증 리포트 Markdown 다운로드",
            data=report_text.encode("utf-8"),
            file_name="field_validation_report.md",
            mime="text/markdown",
        )
        with st.expander("실증 리포트 본문"):
            st.markdown(report_text)

def render_thesis_evidence_tab() -> None:
    """Show thesis evidence artifacts only in the admin console."""
    st.subheader("논문 검증 근거")
    st.caption(
        "상용 제품보다 우월하다는 주장이 아니라, 동일 데이터셋 비교와 제품 workflow 통합성을 방어 가능하게 정리합니다."
    )

    render_comparison_evidence()

    industrial_evidence = load_optional_markdown(OPTIONAL_FILES["industrial_engineering_evidence"])
    if industrial_evidence:
        with st.expander("산업공학 검증 근거 요약"):
            st.markdown(industrial_evidence)

    st.markdown("#### 운영 가치 시뮬레이션")
    if OPTIONAL_FILES["operational_value_comparison"].exists():
        value_df = pd.read_csv(OPTIONAL_FILES["operational_value_comparison"])
        display_columns = [
            "scenario_id",
            "display_name",
            "precision",
            "recall",
            "f1_score",
            "alert_count",
            "false_alarm_count",
            "missed_failure_count",
            "normalized_operating_cost",
        ]
        st.dataframe(value_df[display_columns], width="stretch", hide_index=True)
    else:
        st.info("`src\\evaluate_operational_value.py` 실행 후 운영 가치 시뮬레이션이 표시됩니다.")
    if OPTIONAL_FILES["operational_value_chart"].exists():
        st.image(
            str(OPTIONAL_FILES["operational_value_chart"]),
            caption="Normalized operating cost simulation",
            width="stretch",
        )
    value_summary = load_optional_markdown(OPTIONAL_FILES["operational_value_summary"])
    if value_summary:
        with st.expander("운영 가치 시뮬레이션 요약"):
            st.markdown(value_summary)

    st.markdown("#### 제품 기능 중심 비교")
    if OPTIONAL_FILES["product_capability_comparison"].exists():
        product_df = pd.read_csv(OPTIONAL_FILES["product_capability_comparison"])
        display_columns = [
            "system",
            "category",
            "sensor_input",
            "spc_integration",
            "explainability",
            "work_order_workflow",
            "deployment_level",
            "research_reproducibility",
        ]
        st.dataframe(product_df[display_columns], width="stretch", hide_index=True)
    product_summary = load_optional_markdown(OPTIONAL_FILES["product_capability_summary"])
    if product_summary:
        with st.expander("제품 기능 비교 요약"):
            st.markdown(product_summary)

    st.markdown("#### Workflow traceability")
    if OPTIONAL_FILES["workflow_traceability_comparison"].exists():
        trace_df = pd.read_csv(OPTIONAL_FILES["workflow_traceability_comparison"])
        st.dataframe(trace_df, width="stretch", hide_index=True)
    trace_summary = load_optional_markdown(OPTIONAL_FILES["workflow_traceability_summary"])
    if trace_summary:
        with st.expander("승인형 작업지시 traceability 요약"):
            st.markdown(trace_summary)

    st.markdown("#### 전처리·예측 엔진 상세")
    if OPTIONAL_FILES["company_input_quality_report"].exists():
        quality_df = pd.read_csv(OPTIONAL_FILES["company_input_quality_report"])
        st.dataframe(quality_df, width="stretch", hide_index=True)
    preprocessing_report = load_optional_markdown(OPTIONAL_FILES["company_preprocessing_report"])
    if preprocessing_report:
        with st.expander("회사 CSV 전처리 리포트"):
            st.markdown(preprocessing_report)

    if OPTIONAL_FILES["probability_calibration_metrics"].exists():
        calibration_metrics = load_json(OPTIONAL_FILES["probability_calibration_metrics"])
        st.json(calibration_metrics)
    if OPTIONAL_FILES["probability_calibration_curve"].exists():
        st.image(
            str(OPTIONAL_FILES["probability_calibration_curve"]),
            caption="Probability calibration curve",
            width="stretch",
        )
    confidence_report = load_optional_markdown(OPTIONAL_FILES["prediction_confidence_report"])
    if confidence_report:
        with st.expander("예측 신뢰도 리포트"):
            st.markdown(confidence_report)

    if OPTIONAL_FILES["operating_policy_thresholds"].exists():
        policy_payload = load_json(OPTIONAL_FILES["operating_policy_thresholds"])
        policy_rows = [
            {"policy": policy_id, **policy}
            for policy_id, policy in policy_payload.get("policies", {}).items()
        ]
        if policy_rows:
            st.dataframe(pd.DataFrame(policy_rows), width="stretch", hide_index=True)
    if OPTIONAL_FILES["company_risk_priority_queue"].exists():
        queue_df = pd.read_csv(OPTIONAL_FILES["company_risk_priority_queue"])
        st.dataframe(queue_df.head(30), width="stretch", hide_index=True)
    policy_report = load_optional_markdown(OPTIONAL_FILES["operating_policy_simulation"])
    if policy_report:
        with st.expander("운영 정책 시뮬레이션"):
            st.markdown(policy_report)

    evidence_pack = load_optional_markdown(OPTIONAL_FILES["thesis_evidence_pack"])
    if evidence_pack:
        st.markdown("#### Thesis evidence pack")
        st.markdown(evidence_pack)


def render_final_demo_tab(
    metrics: dict,
    threshold_summary: dict,
    predictions: pd.DataFrame,
    spc_summary: dict,
    ai_context: dict,
    genai_settings: dict,
) -> None:
    """Render a compact first tab for final presentation flow."""
    xgboost = metrics["models"]["xgboost"]
    selected_threshold = float(threshold_summary["selected_threshold"])
    high_risk_count = int((predictions["xgboost_probability"] >= selected_threshold).sum())
    actual_failures = int(predictions["actual_machine_failure"].sum())
    report_mode = str(ai_context.get("report_generation_mode", "not generated"))

    st.subheader("최종발표 Demo")
    st.caption(
        "센서 데이터 입력부터 그래프, 리포트, 승인형 작업지시까지 발표 흐름을 한 번에 요약합니다."
    )

    st.markdown("#### 최종발표 시연 동선")
    step_col1, step_col2, step_col3, step_col4 = st.columns(4)
    with step_col1:
        metric_card("1. API key", "선택", "사이드바에 입력")
    with step_col2:
        metric_card("2. CSV 업로드", "필수", "샘플 CSV 제공")
    with step_col3:
        metric_card("3. 예측/그래프", "자동", "확률·SPC·SHAP")
    with step_col4:
        metric_card("4. 작업지시 승인", "선택", "approve/review/reject")

    st.markdown("#### 입력하면 나오는 것")
    st.dataframe(
        pd.DataFrame(
            [
                {"출력": "고장 확률", "설명": "각 row의 XGBoost failure probability"},
                {"출력": "High Risk 판정", "설명": f"선택 threshold {selected_threshold:.2f} 기준"},
                {"출력": "그래프", "설명": "업로드 row 확률 bar chart, SPC trend/control chart, SHAP 요인"},
                {"출력": "GenAI 리포트", "설명": "API key가 있으면 Gemini/OpenAI 관리자 참고 리포트 생성"},
                {"출력": "작업지시 workflow", "설명": "field-event, draft, approve/reject/needs_review 기록"},
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    st.info("업로드 데이터 예측은 `CSV 업로드 예측` 탭에서 수행합니다. 이 탭은 발표 첫 화면용 요약입니다.")

    st.markdown("#### 현재 검증 상태")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Best Model", "XGBoost", f"PR-AUC {xgboost['pr_auc']:.4f}")
    with col2:
        metric_card("Threshold", f"{selected_threshold:.2f}", "F1-score 기준")
    with col3:
        metric_card("High Risk Rows", str(high_risk_count), f"actual failures {actual_failures}")
    with col4:
        metric_card("GenAI Mode", report_mode.split(":")[0], report_mode)

    with st.expander("발표 클릭 순서 보기"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "순서": 1,
                        "탭": "CSV 업로드 예측",
                        "보여줄 것": "샘플 CSV 다운로드, 업로드 후 예측 결과와 확률 그래프",
                    },
                    {
                        "순서": 2,
                        "탭": "Predictive SPC",
                        "보여줄 것": "시간축 playback, risk trend, control chart",
                    },
                    {
                        "순서": 3,
                        "탭": "GenAI 리포트",
                        "보여줄 것": "Gemini/OpenAI 기반 관리자 참고 리포트",
                    },
                    {
                        "순서": 4,
                        "탭": "운영 PoC",
                        "보여줄 것": "field-event, 작업지시 초안, operator decision 기록",
                    },
                    {
                        "순서": 5,
                        "탭": "한계와 확장",
                        "보여줄 것": "비교 실험과 로컬 PoC 범위",
                    },
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 핵심 그래프")
    col1, col2 = st.columns(2)
    with col1:
        st.image(str(REQUIRED_FILES["spc_risk_chart"]), caption="Predictive SPC risk trend", width="stretch")
    with col2:
        st.image(str(REQUIRED_FILES["shap_bar"]), caption="SHAP feature importance", width="stretch")

    st.download_button(
        "발표용 샘플 CSV 다운로드",
        data=csv_download_bytes(sample_field_dataframe()),
        file_name="sample_field_sensor_rows.csv",
        mime="text/csv",
    )
    st.info(
        "발표 표현은 'Stage 1~20 로컬 통합 PoC'입니다. 실제 PLC/SCADA/클라우드 배포 완료로 말하지 않습니다."
    )


def render_development_tab_overview() -> None:
    """Show a small warning before detailed development-only tabs."""
    st.info(
        "개발/검증 상세 탭은 발표 준비와 산출물 확인용입니다. "
        "최종발표 시연은 사이드바 옵션을 끄고 기본 7개 탭만 사용하는 것을 권장합니다."
    )

def render_limitations_tab(stage9_applicability: str, stage19_20_design: str, final_roadmap: str) -> None:
    """Render thesis-safe limitations and next expansion notes."""
    st.subheader("한계와 확장 계획")
    st.markdown(
        """
        - 현재 구현은 공개 AI4I 데이터와 로컬 파일/API/SQLite 기반 PoC입니다.
        - 실시간 공장 센서, PLC/SCADA, MQTT/OPC UA, 클라우드 운영 배포는 아직 완료 범위가 아닙니다.
        - GenAI 리포트와 작업지시 초안은 관리자 참고용이며 자동 정비 명령이 아닙니다.
        - 실제 현장 적용 전에는 회사별 데이터 매핑, 단위 표준화, threshold 재조정, 권한/감사 로그 설계가 필요합니다.
        """
    )

    st.markdown("#### 실제/샘플 회사 CSV 재검증 시 확인할 항목")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "구분": "데이터 스키마",
                    "확인 내용": "AI4I 호환 센서 컬럼 또는 mapping.json으로 변환 가능한 컬럼인지 확인",
                    "현재 구현": "Stage 14 company adapter와 CSV 업로드 PoC",
                },
                {
                    "구분": "라벨 품질",
                    "확인 내용": "정상/고장 라벨 기준, timestamp, 설비 ID 정의가 일관적인지 확인",
                    "현재 구현": "라벨 있는 회사 CSV 재학습 및 test split 평가",
                },
                {
                    "구분": "불균형 처리",
                    "확인 내용": "기본 모델과 SMOTE 모델의 precision/recall/F1 trade-off 비교",
                    "현재 구현": "model_strategy_comparison 산출물",
                },
                {
                    "구분": "운영 적용성",
                    "확인 내용": "alert 수, false alarm 수, 작업자 승인/보류 이력을 함께 검토",
                    "현재 구현": "SQLite event, work-order draft, operator decision log",
                },
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### 데모 배포 준비 범위")
    st.markdown(
        """
        - Streamlit Cloud 또는 Hugging Face Spaces에는 코드와 공개 산출물만 올리고, API key는 platform secret으로 설정합니다.
        - `outputs/operations.db`, `.venv`, `.env`, 개인 발표 파일, 실제 회사 원본 데이터는 업로드 대상이 아닙니다.
        - 클라우드 배포가 되더라도 이는 발표용 웹 데모이며 실제 공장 운영 배포 완료를 의미하지 않습니다.
        """
    )

    render_comparison_evidence()

    with st.expander("Stage 9 실제 적용성 문서"):
        st.markdown(stage9_applicability)
    with st.expander("Stage 19~20 운영 설계"):
        st.markdown(stage19_20_design)
    with st.expander("최종 단계 로드맵"):
        st.markdown(final_roadmap)


def _legacy_presentation_main() -> None:
    """Run the older presentation dashboard kept for local reference only."""
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

    genai_settings = render_genai_sidebar_settings()

    show_full_dev_tabs = st.sidebar.checkbox(
        "개발/검증 상세 탭 보기",
        value=False,
        help="최종 발표 기본 화면은 핵심 7개 탭만 보여줍니다. 개발/검증용 22개 상세 탭이 필요할 때만 켜세요.",
    )
    st.sidebar.caption("기본값은 최종 발표 모드입니다.")

    if not show_full_dev_tabs:
        tabs = st.tabs(
            [
                "최종 Demo",
                "성과 요약",
                "CSV 업로드 예측",
                "Predictive SPC",
                "GenAI 리포트",
                "운영 PoC",
                "한계와 확장",
            ]
        )

        with tabs[0]:
            render_final_demo_tab(
                metrics,
                threshold_summary,
                predictions,
                spc_summary,
                ai_context,
                genai_settings,
            )
        with tabs[1]:
            render_summary_tab(metrics, threshold_summary)
        with tabs[2]:
            render_field_csv_tab(threshold_summary)
        with tabs[3]:
            render_predictive_spc_tab(spc_summary, spc_timeseries)
        with tabs[4]:
            render_ai_report_tab(
                spc_summary,
                spc_timeseries,
                future_predictions,
                ai_context,
                ai_manager_report,
                genai_settings,
            )
        with tabs[5]:
            render_stage15_20_operations_tab(ai_context)
        with tabs[6]:
            render_limitations_tab(stage9_applicability, stage19_20_design, final_roadmap)
        return

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
            "산업공학 검증 근거",
            "공개 산업 데이터 검증",
            "논문 검증 근거",
            "회사 데이터 실증",
            "로컬 발표/논문 노트",
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
            genai_settings,
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
    with tabs[22]:
        render_industrial_engineering_evidence_tab()
    with tabs[23]:
        render_open_industrial_validation_tab()
    with tabs[24]:
        render_thesis_evidence_tab()
    with tabs[25]:
        render_field_validation_evidence_tab()
    with tabs[26]:
        render_local_notes_tab()


USER_REQUIRED_FILE_KEYS = (
    "metrics",
    "threshold",
    "predictions",
    "spc_timeseries",
    "spc_summary",
    "spc_risk_chart",
    "spc_control_chart",
    "future_predictions",
    "ai_report_context",
    "ai_manager_report",
    "shap_bar",
)

ADMIN_REQUIRED_FILE_KEYS = tuple(REQUIRED_FILES.keys())


def ensure_required_files(file_keys: tuple[str, ...]) -> None:
    """Stop the app with recovery guidance when required outputs are missing."""
    missing_files = [REQUIRED_FILES[key] for key in file_keys if not REQUIRED_FILES[key].exists()]
    if missing_files:
        show_missing_files(missing_files)
        st.stop()


def render_start_tab(
    metrics: dict,
    threshold_summary: dict,
    predictions: pd.DataFrame,
    ai_context: dict,
) -> None:
    """Render the product-style first screen for operators and reviewers."""
    selected_threshold = float(threshold_summary["selected_threshold"])
    high_risk_count = int((predictions["xgboost_probability"] >= selected_threshold).sum())
    report_mode = str(ai_context.get("report_generation_mode", "not generated"))
    report_status, report_note = summarize_report_mode(report_mode)
    actor = current_actor()

    st.subheader("홈")
    st.caption("센서 CSV 업로드부터 위험 확인, AI 리포트, 작업지시 기록까지 한 화면 흐름으로 시작합니다.")

    step_col1, step_col2, step_col3, step_col4 = st.columns(4)
    with step_col1:
        metric_card("CSV 업로드", "1", "샘플 파일 제공")
    with step_col2:
        metric_card("고위험 설비 확인", "2", "확률·High Risk")
    with step_col3:
        metric_card("AI 리포트 생성", "3", "API key 선택")
    with step_col4:
        metric_card("작업지시 승인", "4", "승인·검토·반려")

    st.markdown("#### 입력하면 나오는 것")
    st.dataframe(
        pd.DataFrame(
            [
                {"출력": "고장 확률", "설명": "각 센서 row의 고장 가능성을 확률로 표시"},
                {"출력": "High Risk 판정", "설명": f"위험 판정 기준 {selected_threshold:.2f} 적용"},
                {"출력": "위험 그래프", "설명": "업로드 row 확률 그래프와 관리한계 기반 위험 추세"},
                {"출력": "AI 리포트", "설명": "API key가 있으면 Gemini/OpenAI 기반 관리자 참고 리포트 생성"},
                {"출력": "작업지시 이력", "설명": "센서 이벤트, 초안, 승인/검토/반려 기록"},
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("기준 모델", "XGBoost", "상세 성능은 Admin에서 확인")
    with col2:
        metric_card("위험 판정 기준", f"{selected_threshold:.2f}", "운영 정책에서 조정 가능")
    with col3:
        metric_card("고위험 건수", str(high_risk_count), "기준 데이터에서 확인")
    with col4:
        metric_card("AI 리포트 상태", report_status, report_note)

    st.markdown("#### 운영 준비 상태")
    status_col1, status_col2, status_col3, status_col4 = st.columns(4)
    with status_col1:
        metric_card("로그인", actor.get("role", "unknown"), actor.get("actor_id", "unknown"))
    with status_col2:
        metric_card("운영 DB 상태", "정상" if OPERATIONS_DB_PATH.exists() else "확인 필요", OPERATIONS_DB_PATH.name)
    with status_col3:
        metric_card("감사 로그 상태", "활성", "로그인·예측·작업지시")
    with status_col4:
        metric_card("API key", "세션 한정", "파일 저장 없음")

    col1, col2 = st.columns(2)
    with col1:
        st.image(str(REQUIRED_FILES["spc_risk_chart"]), caption="고장 확률 추세", width="stretch")
    with col2:
        st.image(str(REQUIRED_FILES["shap_bar"]), caption="위험요인 중요도", width="stretch")

    st.download_button(
        "샘플 센서 CSV 다운로드",
        data=csv_download_bytes(sample_field_dataframe()),
        file_name="sample_field_sensor_rows.csv",
        mime="text/csv",
    )

    with st.expander("사용 전 확인사항"):
        st.markdown(
            """
            - 실제 설비에 적용하기 전에는 설비별 센서 주기, 단위, 결측 처리 기준을 확인해야 합니다.
            - 회사 데이터로 성능을 다시 평가하려면 고장 여부가 포함된 labeled CSV가 필요합니다.
            - 이 앱은 사람이 승인하는 작업지시 흐름을 지원하며, 무인 자동 정비 명령을 실행하지 않습니다.
            - API key와 업로드 원본 데이터는 파일로 저장하지 않고 현재 세션 처리에만 사용합니다.
            """
        )


def render_product_summary_tab(metrics: dict, threshold_summary: dict) -> None:
    """Render model quality without presentation-only wording."""
    xgboost = metrics["models"]["xgboost"]
    selected = threshold_summary["selected_metrics"]
    selected_threshold = float(threshold_summary["selected_threshold"])

    st.subheader("성과 요약")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Best Model", "XGBoost", "PR-AUC 기준")
    with col2:
        metric_card("XGBoost PR-AUC", f"{xgboost['pr_auc']:.4f}", "불균형 데이터 평가")
    with col3:
        metric_card("Threshold", f"{selected_threshold:.2f}", "F1-score 기준 선택")
    with col4:
        metric_card("F1-score", f"{selected['f1_score']:.4f}", "선택 threshold 기준")

    st.markdown(
        f"""
        <div class="callout">
        이 대시보드는 공개 AI4I 2020 데이터로 학습된 예지보전 모델을 사용합니다.
        XGBoost가 PR-AUC 기준 대표 모델이며, threshold {selected_threshold:.2f}를 기준으로
        High Risk row를 구분합니다. 실제 사업장 적용 전에는 회사 데이터로 threshold와 성능을 다시 검증해야 합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scope_tab() -> None:
    """Render product-scope notes without mixing in development tabs."""
    st.subheader("적용 범위")
    st.markdown(
        """
        이 앱은 센서 CSV 기반 예지보전 의사결정을 지원하는 로컬 운영형 애플리케이션입니다.

        - 지원 입력: AI4I-compatible 센서 CSV 또는 화면 직접 입력 row
        - 지원 출력: 고장 확률, High Risk 판정, 위험 모니터링 그래프, 위험요인, AI 관리자 참고 리포트, 승인형 작업지시 이력
        - 저장 이력: 로컬 SQLite와 CSV export
        - AI API key: 현재 Streamlit 세션에서만 사용하며 파일에 저장하지 않음

        아직 포함하지 않는 범위:

        - 실제 PLC/SCADA 운영망 연결 완료
        - 실제 공장 센서 스트림 운영 배포
        - 무인 자동 정비 명령 실행
        - 상용 SaaS 수준의 OAuth/SSO/MFA, 외부 운영 DB, 보안 감사, 장애 대응 체계
        - 현장 회사 데이터 기반 성능 실증 수치
        """
    )

    st.markdown("#### 현재 반영된 운영 기능")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "영역": "로그인/역할",
                    "반영 상태": "Operator 앱과 Admin 콘솔 분리",
                    "한계": "기업용 OAuth/SSO/MFA는 별도 범위",
                },
                {
                    "영역": "감사 로그",
                    "반영 상태": "로그인, CSV 예측, AI 리포트 시도, 센서 이벤트, 작업지시 결정 기록",
                    "한계": "외부 보안 감사 시스템 연동은 별도 범위",
                },
                {
                    "영역": "운영 DB",
                    "반영 상태": "SQLite에 event, draft, decision, audit log 저장",
                    "한계": "PostgreSQL/RDS/Supabase 운영 DB는 계정 정보 필요",
                },
                {
                    "영역": "작업지시",
                    "반영 상태": "승인, 검토 필요, 반려 결정과 재학습 후보 표시",
                    "한계": "CMMS/EAM 자동 연동과 자동 정비 명령은 제외",
                },
                {
                    "영역": "입력 데이터",
                    "반영 상태": "컬럼 자동 매핑, 단위 변환, 결측/이상값/중복 진단",
                    "한계": "실제 회사 성능 검증은 labeled company CSV 필요",
                },
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### 산업공학 지표 연결")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "개념": "OEE",
                    "앱에서의 연결": "고위험 설비 조기 확인을 통해 Availability 관리와 연결 가능",
                    "주의": "현재 데이터만으로 실제 OEE 개선을 실증하지 않음",
                },
                {
                    "개념": "MTBF / MTTR",
                    "앱에서의 연결": "고장 위험 이벤트와 작업지시 이력을 축적하면 향후 평균고장간격/평균수리시간 분석 가능",
                    "주의": "실제 수리 시작/종료 로그가 필요",
                },
                {
                    "개념": "FMEA / RPN",
                    "앱에서의 연결": "risk_priority_score를 Severity, Occurrence, Detection 관점으로 해석 가능",
                    "주의": "표준 FMEA 점수를 대체하지 않는 FMEA-inspired 우선순위",
                },
                {
                    "개념": "SPC 관리한계",
                    "앱에서의 연결": "고장 확률과 주요 센서 신호를 UCL 중심으로 모니터링",
                    "주의": "현장 정상 기간 데이터로 관리한계를 다시 설정해야 함",
                },
                {
                    "개념": "Cost simulation",
                    "앱에서의 연결": "false alarm, missed failure, alert 처리에 상대 가중치를 둔 정책 비교",
                    "주의": "실제 비용 절감 실증이 아니라 normalized simulation",
                },
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### 검증된 범위와 금지 표현")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "구분": "가능",
                    "표현": "동일 AI4I split에서 모델, SMOTE, threshold, SPC alert 정책을 비교했다.",
                },
                {
                    "구분": "가능",
                    "표현": "SHAP/AI 리포트 설명과 승인형 작업지시 workflow를 하나의 흐름으로 연결했다.",
                },
                {
                    "구분": "가능",
                    "표현": "false alarm과 missed failure에 가중치를 둔 normalized cost simulation을 수행했다.",
                },
                {
                    "구분": "금지",
                    "표현": "실제 공장에서 비용 절감, 시간 단축, 자동 정비 명령 실행이 검증됐다고 말하지 않는다.",
                },
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    st.info("세부 비교표와 연구 근거 자료는 사용자 앱이 아니라 Admin 콘솔에서 확인합니다.")


def render_work_order_tab(ai_context: dict) -> None:
    """Render product-style field event and work-order workflow."""
    st.subheader("작업지시")
    st.caption("센서 row 입력부터 이벤트 생성, 작업지시 초안, 승인/검토/반려 기록까지 한 흐름으로 관리합니다.")

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
    report_status, report_note = summarize_report_mode(report_mode)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("AI 리포트 상태", report_status, report_note)
    with col2:
        metric_card("센서 이벤트", str(len(field_events)), "저장 기록")
    with col3:
        metric_card("작업지시 초안", str(len(drafts)), "승인 대기")
    with col4:
        metric_card("결정 이력", str(len(decisions)), "승인·검토·반려")

    render_stage19_20_input_controls(events, drafts)

    st.markdown("#### 최근 센서 이벤트")
    if events:
        event_rows = []
        for event in events:
            top_factor = event.get("top_shap_factors", [{}])[0].get("feature", "")
            event_input = event.get("input", {})
            event_rows.append(
                {
                    "생성 시각": event["created_at"],
                    "설비 ID": event_input.get("equipment_id", ""),
                    "이벤트 시각": event_input.get("event_timestamp", ""),
                    "이벤트": event["event_id"][:8],
                    "고장 확률": event["probability"],
                    "위험 기준": event["threshold"],
                    "위험 상태": event["risk_status"],
                    "주요 요인": top_factor,
                }
            )
        st.dataframe(pd.DataFrame(event_rows), width="stretch", hide_index=True)
        with st.expander("센서 이벤트 상세 ID 보기"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "event_id": event["event_id"],
                            "source": event["source"],
                            "equipment_id": event.get("input", {}).get("equipment_id", ""),
                        }
                        for event in events
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info("아직 저장된 센서 이벤트가 없습니다.")

    st.markdown("#### 최근 작업지시 초안")
    if drafts:
        draft_rows = [
            {
                "생성 시각": draft["created_at"],
                "초안": draft["draft_id"][:8],
                "센서 이벤트": draft["event_id"][:8],
                "사람 승인 필요": draft["draft_json"].get("requires_human_approval"),
            }
            for draft in drafts
        ]
        st.dataframe(pd.DataFrame(draft_rows), width="stretch", hide_index=True)
        with st.expander("작업지시 초안 상세 ID 보기"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "draft_id": draft["draft_id"],
                            "event_id": draft["event_id"],
                            "draft_path": draft["draft_path"],
                        }
                        for draft in drafts
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info("아직 생성된 작업지시 초안이 없습니다.")

    st.markdown("#### 최근 승인/검토/반려 기록")
    if decisions:
        def safe_operator_note(value: str) -> str:
            """Keep product UI free from internal project wording in old notes."""
            replacements = {
                "Stage": "단계",
                "PoC": "MVP",
                "Demo": "시연",
                "발표": "시연",
                "논문": "문서",
                "캡스톤": "프로젝트",
                "검증": "확인",
            }
            text = str(value or "")
            for source, target in replacements.items():
                text = text.replace(source, target)
            return text

        action_labels = {
            "approve": "승인: 작업자가 현장 조치를 진행할 수 있음",
            "reject": "반려: 초안을 실행하지 않음",
            "needs_review": "검토 필요: 관리자 재검토와 재학습 후보로 표시",
        }
        decision_rows = [
            {
                "생성 시각": decision["created_at"],
                "결정": decision["decision_id"][:8],
                "초안": decision["draft_id"][:8],
                "센서 이벤트": decision["event_id"][:8],
                "작업자": decision["operator_id"],
                "결정값": decision["decision"],
                "조치 이력": action_labels.get(decision["decision"], "기록됨"),
                "재학습 후보": decision["decision"] == "needs_review",
                "메모": safe_operator_note(decision["note"]),
            }
            for decision in decisions
        ]
        st.dataframe(pd.DataFrame(decision_rows), width="stretch", hide_index=True)
        with st.expander("결정 이력 상세 ID 보기"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "decision_id": decision["decision_id"],
                            "draft_id": decision["draft_id"],
                            "event_id": decision["event_id"],
                        }
                        for decision in decisions
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        if WORK_ORDER_DECISIONS_PATH.exists():
            st.download_button(
                "작업지시 결정 이력 CSV 다운로드",
                data=WORK_ORDER_DECISIONS_PATH.read_bytes(),
                file_name="work_order_decisions.csv",
                mime="text/csv",
            )
    else:
        st.info("아직 승인/검토/반려 기록이 없습니다.")


def scan_api_key_patterns() -> list[dict]:
    """Scan repo text artifacts for accidental API key-like strings."""
    patterns = [
        re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    ]
    excluded_parts = {".git", ".venv", "__pycache__"}
    suffixes = {".py", ".md", ".ps1", ".bat", ".json", ".csv", ".txt", ".toml", ".yml", ".yaml"}
    hits = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in excluded_parts for part in path.parts):
            continue
        if path.name == "operations.db":
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for line_number, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in patterns):
                hits.append(
                    {
                        "path": str(path.relative_to(PROJECT_ROOT)),
                        "line": line_number,
                        "preview": line[:120],
                    }
                )
    return hits


def render_admin_monitoring(ai_context: dict) -> None:
    """Render product MVP health, audit, and artifact monitoring."""
    st.subheader("운영 모니터링")
    events = list_prediction_events(limit=1000, db_path=OPERATIONS_DB_PATH)
    drafts = list_work_order_drafts(limit=1000, db_path=OPERATIONS_DB_PATH)
    decisions = list_work_order_decisions(limit=1000, db_path=OPERATIONS_DB_PATH)
    audit_logs = list_audit_logs(limit=1000, db_path=OPERATIONS_DB_PATH)
    failures = [entry for entry in audit_logs if entry["status"] == "failure"]
    report_mode = str(ai_context.get("report_generation_mode", "not generated"))

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        metric_card("DB", "OK" if OPERATIONS_DB_PATH.exists() else "Missing", OPERATIONS_DB_PATH.name)
    with col2:
        metric_card("Events", str(len(events)), "prediction events")
    with col3:
        metric_card("Drafts", str(len(drafts)), "work orders")
    with col4:
        metric_card("Decisions", str(len(decisions)), "operator log")
    with col5:
        metric_card("Audit Failures", str(len(failures)), "recent log")

    st.markdown("#### 주요 산출물 상태")
    artifact_rows = []
    for key, path in REQUIRED_FILES.items():
        artifact_rows.append(
            {
                "artifact": key,
                "exists": path.exists(),
                "path": str(path.relative_to(PROJECT_ROOT)),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
                if path.exists()
                else "",
            }
        )
    st.dataframe(pd.DataFrame(artifact_rows), width="stretch", hide_index=True)

    st.markdown("#### GenAI / 보안 상태")
    key_hits = scan_api_key_patterns()
    security_rows = [
        {"check": "report_generation_mode", "status": report_mode},
        {"check": "API key pattern scan", "status": "PASS" if not key_hits else f"FAIL: {len(key_hits)} hit(s)"},
        {"check": "operations_db", "status": str(OPERATIONS_DB_PATH)},
    ]
    st.dataframe(pd.DataFrame(security_rows), width="stretch", hide_index=True)
    if key_hits:
        st.error("API key처럼 보이는 문자열이 발견되었습니다. GitHub push 전에 제거해야 합니다.")
        st.dataframe(pd.DataFrame(key_hits), width="stretch", hide_index=True)

    st.markdown("#### 최근 감사 로그")
    if audit_logs:
        audit_df = pd.DataFrame(audit_logs)
        display_columns = [
            "created_at",
            "actor_id",
            "role",
            "action",
            "status",
            "target_type",
            "target_id",
            "error_message",
        ]
        st.dataframe(audit_df[display_columns].head(100), width="stretch", hide_index=True)
    else:
        st.info("아직 감사 로그가 없습니다.")


def render_local_notes_tab() -> None:
    """Render local-only presentation and thesis notes when they exist."""
    st.subheader("로컬 발표/논문 노트")
    st.caption(
        "이 자료는 로컬 폴더에만 보관합니다. local_presentation_notes/는 .gitignore 대상이므로 GitHub에 업로드하지 않습니다."
    )

    note_rows = []
    for note_id, path in LOCAL_NOTE_FILES.items():
        note_rows.append(
            {
                "note": note_id,
                "exists": path.exists(),
                "path": str(path.relative_to(PROJECT_ROOT)),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
                if path.exists()
                else "",
            }
        )
    st.dataframe(pd.DataFrame(note_rows), width="stretch", hide_index=True)

    for note_id, path in LOCAL_NOTE_FILES.items():
        if not path.exists():
            continue
        with st.expander(note_id.replace("_", " ").title(), expanded=note_id == "industrial_engineering_notes"):
            st.markdown(path.read_text(encoding="utf-8"))


def render_user_app() -> None:
    """Render the product MVP dashboard only."""
    ensure_required_files(USER_REQUIRED_FILE_KEYS)
    metrics = load_json(REQUIRED_FILES["metrics"])
    threshold_summary = load_json(REQUIRED_FILES["threshold"])
    predictions = load_predictions(REQUIRED_FILES["predictions"])
    spc_timeseries = load_csv(REQUIRED_FILES["spc_timeseries"])
    spc_summary = load_json(REQUIRED_FILES["spc_summary"])
    future_predictions = load_csv(REQUIRED_FILES["future_predictions"])
    ai_context = load_json(REQUIRED_FILES["ai_report_context"])
    ai_manager_report = load_markdown(REQUIRED_FILES["ai_manager_report"])
    genai_settings = render_genai_sidebar_settings()

    tabs = st.tabs(
        [
            "홈",
            "데이터 예측",
            "위험 모니터링",
            "AI 리포트",
            "작업지시",
        ]
    )
    with tabs[0]:
        render_start_tab(metrics, threshold_summary, predictions, ai_context)
    with tabs[1]:
        render_field_csv_tab(threshold_summary)
    with tabs[2]:
        render_predictive_spc_tab(spc_summary, spc_timeseries)
    with tabs[3]:
        render_ai_report_tab(
            spc_summary,
            spc_timeseries,
            future_predictions,
            ai_context,
            ai_manager_report,
            genai_settings,
        )
    with tabs[4]:
        render_work_order_tab(ai_context)


def render_admin_app() -> None:
    """Render the separated development and verification console."""
    ensure_required_files(ADMIN_REQUIRED_FILE_KEYS)
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
    genai_settings = render_genai_sidebar_settings()

    render_admin_monitoring(ai_context)

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
            "산업공학 검증 근거",
            "공개 산업 데이터 검증",
            "논문 검증 근거",
            "로컬 발표/논문 노트",
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
            genai_settings,
        )
    with tabs[8]:
        render_field_csv_tab(threshold_summary)
    with tabs[9]:
        render_company_retraining_tab()
    with tabs[10]:
        render_markdown_tab("개별 고장 예측 사례", local_case)
    with tabs[11]:
        render_markdown_tab("중간발표 진행안", midterm_guide)
    with tabs[12]:
        render_markdown_tab("중간발표 예상 질문 답변", midterm_qna)
    with tabs[13]:
        render_markdown_tab("발표 요약", presentation_summary)
    with tabs[14]:
        render_markdown_tab("캡스톤 연구 Stage 보완안", research_plan)
    with tabs[15]:
        render_markdown_tab("리허설 체크리스트", rehearsal_checklist)
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
    with tabs[22]:
        render_industrial_engineering_evidence_tab()
    with tabs[23]:
        render_open_industrial_validation_tab()
    with tabs[24]:
        render_thesis_evidence_tab()
    with tabs[25]:
        render_local_notes_tab()


def main(app_mode: str = "user") -> None:
    """Run either the product MVP dashboard or the separated admin console."""
    is_admin = app_mode == "admin"
    configure_page(
        page_title=(
            "연구 검증 Admin Console"
            if is_admin
            else "AI 예지보전 운영 대시보드"
        )
    )
    render_header(
        badge="연구 검증 콘솔" if is_admin else "운영 대시보드",
        title=(
            "연구 검증 Admin Console"
            if is_admin
            else "AI 예지보전 운영 대시보드"
        ),
        subtitle=(
            "모델 실험, 검증 산출물, 연구 문서, 운영 이력 상태를 별도 콘솔에서 확인합니다."
            if is_admin
            else "센서 CSV를 기반으로 고장 확률, 위험 우선순위, AI 리포트, 작업지시 이력을 관리합니다."
        ),
    )
    actor = require_login("admin" if is_admin else "operator")
    st.sidebar.success(f"로그인: {actor['actor_id']} ({actor['role']})")
    if st.sidebar.button("로그아웃", key=f"{actor['role']}_logout"):
        record_audit("auth.logout", "success", "session", actor["role"], actor=actor)
        st.session_state.pop(f"{actor['role']}_authenticated", None)
        st.session_state.pop("auth_user", None)
        st.rerun()
    if is_admin:
        render_admin_app()
    else:
        render_user_app()


if __name__ == "__main__":
    main()
