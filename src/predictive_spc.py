import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import matplotlib
import pandas as pd


matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

PREDICTIONS_PATH = OUTPUT_DIR / "baseline_predictions.csv"
THRESHOLD_PATH = OUTPUT_DIR / "threshold_summary.json"
LOCAL_CASE_PATH = OUTPUT_DIR / "local_case_explanation.json"

SPC_TIMESERIES_PATH = OUTPUT_DIR / "spc_timeseries.csv"
SPC_SUMMARY_PATH = OUTPUT_DIR / "spc_summary.json"
SPC_RISK_CHART_PATH = OUTPUT_DIR / "spc_risk_chart.png"
SPC_CONTROL_CHART_PATH = OUTPUT_DIR / "spc_control_chart.png"
AI_CONTEXT_PATH = OUTPUT_DIR / "ai_report_context.json"
AI_REPORT_PATH = OUTPUT_DIR / "ai_manager_report.md"
FUTURE_PREDICTIONS_PATH = OUTPUT_DIR / "future_deviation_predictions.csv"
FUTURE_METRICS_PATH = OUTPUT_DIR / "future_deviation_metrics.json"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
GEMINI_GENERATE_CONTENT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_FALLBACK_MODELS = ["gemini-2.5-flash-lite"]
DEFAULT_AI_REPORT_PROVIDER = "gemini"
TRANSIENT_API_STATUS_CODES = {429, 500, 502, 503, 504}

ROLLING_WINDOW = 50
SIMULATION_START = "2026-06-01 08:00:00"
SIMULATION_FREQ = "min"


def load_json(path: Path) -> dict:
    """Load a JSON artifact and fail clearly when it is missing."""
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_file(path: Path) -> None:
    """Make missing prerequisite artifacts easy to diagnose."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}\n"
            "Run train_baseline.py and stage4_explain.py before creating SPC outputs."
        )


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Load the saved prediction result, raw AI4I data, threshold, and SHAP case."""
    require_file(PREDICTIONS_PATH)
    require_file(DATA_PATH)
    require_file(THRESHOLD_PATH)
    require_file(LOCAL_CASE_PATH)

    predictions = pd.read_csv(PREDICTIONS_PATH)
    raw_data = pd.read_csv(DATA_PATH)
    threshold_summary = load_json(THRESHOLD_PATH)
    local_case = load_json(LOCAL_CASE_PATH)
    return predictions, raw_data, threshold_summary, local_case


def build_spc_timeseries(
    predictions: pd.DataFrame,
    raw_data: pd.DataFrame,
    selected_threshold: float,
    rolling_window: int = ROLLING_WINDOW,
) -> pd.DataFrame:
    """
    Convert saved test predictions into a presentation-safe time-series simulation.

    AI4I is not a live sensor stream in this project, so UDI order is used as a
    transparent simulated time axis for final presentation and paper discussion.
    """
    sensor_columns = [
        "UDI",
        "Product ID",
        "Type",
        "Air temperature [K]",
        "Process temperature [K]",
        "Rotational speed [rpm]",
        "Torque [Nm]",
        "Tool wear [min]",
        "Machine failure",
    ]
    merged = predictions.merge(
        raw_data[sensor_columns],
        on=["UDI", "Product ID"],
        how="left",
        suffixes=("", "_raw"),
    )
    merged = merged.sort_values("UDI").reset_index(drop=True)
    merged.insert(0, "time_step", range(1, len(merged) + 1))
    merged.insert(
        1,
        "simulated_timestamp",
        pd.date_range(SIMULATION_START, periods=len(merged), freq=SIMULATION_FREQ),
    )

    probabilities = merged["xgboost_probability"].astype(float)
    merged["selected_threshold"] = float(selected_threshold)
    merged["risk_status"] = probabilities.apply(
        lambda value: "High Risk" if value >= selected_threshold else "Normal"
    )
    merged["risk_rolling_mean"] = probabilities.rolling(
        window=rolling_window,
        min_periods=1,
    ).mean()

    risk_center = float(probabilities.mean())
    risk_std = float(probabilities.std(ddof=0))
    merged["risk_center_line"] = risk_center
    merged["risk_ucl"] = min(1.0, risk_center + (3 * risk_std))
    merged["risk_lcl"] = max(0.0, risk_center - (3 * risk_std))
    merged["risk_beyond_control_limit"] = (
        (probabilities > merged["risk_ucl"]) | (probabilities < merged["risk_lcl"])
    )
    merged["spc_risk_alert"] = (
        (probabilities >= selected_threshold) | merged["risk_beyond_control_limit"]
    )

    torque = merged["Torque [Nm]"].astype(float)
    torque_center = float(torque.mean())
    torque_std = float(torque.std(ddof=0))
    merged["torque_rolling_mean"] = torque.rolling(
        window=rolling_window,
        min_periods=1,
    ).mean()
    merged["torque_center_line"] = torque_center
    merged["torque_ucl"] = torque_center + (3 * torque_std)
    merged["torque_lcl"] = torque_center - (3 * torque_std)
    merged["torque_beyond_control_limit"] = (
        (torque > merged["torque_ucl"]) | (torque < merged["torque_lcl"])
    )

    return merged


def summarize_spc(spc_df: pd.DataFrame, selected_threshold: float) -> dict:
    """Create the small JSON summary used by the dashboard and final paper."""
    high_risk_rows = spc_df[spc_df["risk_status"] == "High Risk"]
    spc_alert_rows = spc_df[spc_df["spc_risk_alert"]]
    torque_alert_rows = spc_df[spc_df["torque_beyond_control_limit"]]

    return {
        "source": "AI4I 2020 test predictions with UDI-order simulated time axis",
        "note": (
            "This is a presentation-safe time-series simulation, not a live "
            "factory sensor stream."
        ),
        "selected_threshold": float(selected_threshold),
        "rolling_window": int(ROLLING_WINDOW),
        "total_rows": int(len(spc_df)),
        "high_risk_count": int(len(high_risk_rows)),
        "spc_risk_alert_count": int(len(spc_alert_rows)),
        "actual_failure_count": int(spc_df["actual_machine_failure"].sum()),
        "risk_mean": round(float(spc_df["xgboost_probability"].mean()), 6),
        "risk_ucl": round(float(spc_df["risk_ucl"].iloc[0]), 6),
        "risk_lcl": round(float(spc_df["risk_lcl"].iloc[0]), 6),
        "max_probability": round(float(spc_df["xgboost_probability"].max()), 6),
        "max_probability_udi": int(
            spc_df.loc[spc_df["xgboost_probability"].idxmax(), "UDI"]
        ),
        "torque_center_line": round(float(spc_df["torque_center_line"].iloc[0]), 6),
        "torque_ucl": round(float(spc_df["torque_ucl"].iloc[0]), 6),
        "torque_lcl": round(float(spc_df["torque_lcl"].iloc[0]), 6),
        "torque_beyond_control_limit_count": int(len(torque_alert_rows)),
    }


def add_future_deviation_summary(spc_summary: dict) -> dict:
    """Preserve future-deviation summary when SPC outputs are regenerated."""
    if not FUTURE_METRICS_PATH.exists():
        return spc_summary

    metrics = load_json(FUTURE_METRICS_PATH)
    summary = metrics.get("summary", {})
    classification = metrics.get("classification", {})
    regression = metrics.get("regression", {})

    spc_summary["future_deviation"] = {
        "horizon_steps": int(metrics["horizon_steps"]),
        "predicted_future_deviation_rows": int(
            summary["predicted_future_deviation_rows"]
        ),
        "max_predicted_future_risk": float(summary["max_predicted_future_risk"]),
        "max_predicted_future_risk_time_step": int(
            summary["max_predicted_future_risk_time_step"]
        ),
        "classification_f1_score": classification["f1_score"],
        "regression_rmse": regression["rmse"],
    }
    return spc_summary


def save_risk_chart(spc_df: pd.DataFrame, output_path: Path) -> None:
    """Plot risk probability over the simulated time axis."""
    high_risk = spc_df[spc_df["risk_status"] == "High Risk"]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(
        spc_df["time_step"],
        spc_df["xgboost_probability"],
        color="#1f77b4",
        linewidth=1.1,
        label="XGBoost failure probability",
    )
    ax.plot(
        spc_df["time_step"],
        spc_df["risk_rolling_mean"],
        color="#0f766e",
        linewidth=2.0,
        label=f"Rolling mean ({ROLLING_WINDOW} rows)",
    )
    ax.axhline(
        spc_df["selected_threshold"].iloc[0],
        color="#b42318",
        linestyle="--",
        linewidth=1.6,
        label="Selected threshold",
    )
    ax.axhline(
        spc_df["risk_ucl"].iloc[0],
        color="#c97700",
        linestyle=":",
        linewidth=1.6,
        label="Risk UCL",
    )
    if not high_risk.empty:
        ax.scatter(
            high_risk["time_step"],
            high_risk["xgboost_probability"],
            color="#b42318",
            s=18,
            label="High Risk rows",
            zorder=5,
        )

    ax.set_title("Predictive SPC Risk Signal over Simulated Time")
    ax.set_xlabel("Simulated time step by UDI order")
    ax.set_ylabel("Failure probability")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_control_chart(spc_df: pd.DataFrame, output_path: Path) -> None:
    """Plot a simple control chart for torque, the main SHAP factor."""
    torque_alerts = spc_df[spc_df["torque_beyond_control_limit"]]
    high_risk = spc_df[spc_df["risk_status"] == "High Risk"]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(
        spc_df["time_step"],
        spc_df["Torque [Nm]"],
        color="#344054",
        linewidth=1.1,
        label="Torque [Nm]",
    )
    ax.plot(
        spc_df["time_step"],
        spc_df["torque_rolling_mean"],
        color="#0f766e",
        linewidth=2.0,
        label=f"Rolling mean ({ROLLING_WINDOW} rows)",
    )
    ax.axhline(
        spc_df["torque_center_line"].iloc[0],
        color="#637381",
        linestyle="-",
        linewidth=1.2,
        label="Center line",
    )
    ax.axhline(
        spc_df["torque_ucl"].iloc[0],
        color="#c97700",
        linestyle="--",
        linewidth=1.5,
        label="Torque UCL",
    )
    ax.axhline(
        spc_df["torque_lcl"].iloc[0],
        color="#c97700",
        linestyle="--",
        linewidth=1.5,
        label="Torque LCL",
    )
    if not high_risk.empty:
        ax.scatter(
            high_risk["time_step"],
            high_risk["Torque [Nm]"],
            color="#b42318",
            s=18,
            alpha=0.8,
            label="High Risk rows",
            zorder=5,
        )
    if not torque_alerts.empty:
        ax.scatter(
            torque_alerts["time_step"],
            torque_alerts["Torque [Nm]"],
            facecolors="none",
            edgecolors="#7a2e0e",
            s=54,
            linewidths=1.4,
            label="Torque beyond control limit",
            zorder=6,
        )

    ax.set_title("Predictive SPC Control Chart for Torque")
    ax.set_xlabel("Simulated time step by UDI order")
    ax.set_ylabel("Torque [Nm]")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def top_shap_factors(local_case: dict, limit: int = 3) -> list[dict]:
    """Keep the strongest SHAP factors from the saved local explanation."""
    factors = []
    for item in local_case.get("top_features", [])[:limit]:
        factors.append(
            {
                "feature": item.get("feature", "sensor factor"),
                "feature_value": item.get("feature_value"),
                "shap_value": item.get("shap_value"),
                "direction": item.get("direction", "unknown"),
            }
        )
    return factors


def load_future_context_for_time_step(time_step: int) -> dict:
    """Load future-deviation evidence for one simulated time step when it exists."""
    if not FUTURE_PREDICTIONS_PATH.exists():
        return {}

    future_predictions = pd.read_csv(FUTURE_PREDICTIONS_PATH)
    selected = future_predictions[future_predictions["time_step"] == time_step]
    if selected.empty:
        return {}

    row = selected.iloc[0]
    actual_value = row.get("future_deviation_actual_h10")
    context = {
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

    if FUTURE_METRICS_PATH.exists():
        metrics = load_json(FUTURE_METRICS_PATH)
        context["model_metrics"] = {
            "validation_f1_score": metrics.get("classification", {}).get("f1_score"),
            "validation_pr_auc": metrics.get("classification", {}).get("pr_auc"),
            "regression_rmse": metrics.get("regression", {}).get("rmse"),
        }

    return context


def build_ai_report_context(spc_df: pd.DataFrame, spc_summary: dict, local_case: dict) -> dict:
    """Build a compact, auditable context for LLM or fallback reporting."""
    candidate = spc_df.sort_values("xgboost_probability", ascending=False).iloc[0]
    time_step = int(candidate["time_step"])
    return {
        "report_scope": "manager reference report for final capstone presentation",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "simulation_note": (
            "AI4I rows are ordered by UDI to simulate a time-series stream. "
            "This is not a live factory sensor feed."
        ),
        "row": {
            "time_step": time_step,
            "simulated_timestamp": str(candidate["simulated_timestamp"]),
            "UDI": int(candidate["UDI"]),
            "Product ID": str(candidate["Product ID"]),
            "actual_machine_failure": int(candidate["actual_machine_failure"]),
            "xgboost_probability": round(float(candidate["xgboost_probability"]), 6),
            "selected_threshold": round(float(candidate["selected_threshold"]), 6),
            "risk_status": str(candidate["risk_status"]),
            "risk_beyond_control_limit": bool(candidate["risk_beyond_control_limit"]),
            "torque_beyond_control_limit": bool(candidate["torque_beyond_control_limit"]),
        },
        "sensor_values": {
            "Type": str(candidate["Type"]),
            "Air temperature [K]": round(float(candidate["Air temperature [K]"]), 4),
            "Process temperature [K]": round(float(candidate["Process temperature [K]"]), 4),
            "Rotational speed [rpm]": round(float(candidate["Rotational speed [rpm]"]), 4),
            "Torque [Nm]": round(float(candidate["Torque [Nm]"]), 4),
            "Tool wear [min]": round(float(candidate["Tool wear [min]"]), 4),
        },
        "spc_summary": spc_summary,
        "future_prediction": load_future_context_for_time_step(time_step),
        "top_shap_factors": top_shap_factors(local_case),
        "guardrail": (
            "Use current risk, future 10-step deviation prediction, and SHAP evidence "
            "only as a manager reference. Do not write an automatic maintenance order. "
            "Say final action must be confirmed by field staff."
        ),
    }


def fallback_ai_report(context: dict, reason: str) -> str:
    """Create a deterministic report when no LLM API key is available."""
    row = context["row"]
    sensors = context["sensor_values"]
    factors = context.get("top_shap_factors", [])
    factor_text = ", ".join(item["feature"] for item in factors) or "saved SHAP factors"
    future = context.get("future_prediction") or {}
    future_lines = []
    if future:
        future_status = (
            "미래 이탈 후보"
            if future.get("predicted_future_deviation_h10")
            else "미래 이탈 가능성 낮음"
        )
        future_lines = [
            "",
            "## 3. 미래 10-step 이탈 예측",
            "",
            f"- 예측 horizon: `{future.get('horizon_steps', 10)}` simulated steps",
            f"- 미래 최대 위험 예측값: `{future.get('predicted_future_max_risk_h10', 0):.4f}`",
            f"- 미래 이탈 확률: `{future.get('predicted_future_deviation_probability_h10', 0):.4f}`",
            f"- 판단: `{future_status}`",
        ]

    return "\n".join(
        [
            "# AI 관리자 점검 리포트 초안",
            "",
            f"- 생성 방식: 로컬 템플릿 fallback ({reason})",
            f"- 대상 row: UDI `{row['UDI']}`, time step `{row['time_step']}`",
            f"- 위험 상태: `{row['risk_status']}`",
            f"- 고장 확률: `{row['xgboost_probability']:.4f}` / threshold `{row['selected_threshold']:.2f}`",
            f"- SPC 이상 여부: risk limit `{row['risk_beyond_control_limit']}`, torque limit `{row['torque_beyond_control_limit']}`",
            "",
            "## 1. 요약",
            "",
            "선택된 row는 XGBoost 고장 확률이 threshold를 넘는 High Risk 후보입니다. "
            "이 결과는 실제 센서 스트리밍이 아니라 AI4I 공개 데이터의 UDI 순서를 이용한 시간축 시뮬레이션입니다.",
            "",
            "## 2. 주요 근거",
            "",
            f"- SHAP 기반 주요 요인: {factor_text}",
            f"- Torque [Nm]: `{sensors['Torque [Nm]']}`",
            f"- Rotational speed [rpm]: `{sensors['Rotational speed [rpm]']}`",
            f"- Tool wear [min]: `{sensors['Tool wear [min]']}`",
            *future_lines,
            "",
            "## 4. 관리자 참고 조치",
            "",
            "1. 해당 row의 토크, 회전 속도, 공구 마모 조건이 정상 운전 범위와 다른지 우선 확인합니다.",
            "2. 같은 조건이 반복되는지 최근 High Risk row와 함께 비교합니다.",
            "3. 미래 이탈 후보로 표시되면 다음 10 step 구간을 우선 모니터링 대상으로 둡니다.",
            "4. 실제 정비 지시는 현장 담당자의 설비 상태 확인 후 확정합니다.",
            "",
            "## 5. 한계",
            "",
            "이 리포트는 자동 정비 명령이 아니라 발표용 PoC의 관리자 참고 초안입니다.",
            "",
        ]
    )


def build_llm_prompt(context: dict) -> str:
    """Create a short prompt that keeps the LLM grounded in numeric evidence."""
    return (
        "다음 JSON 근거만 사용해서 한국어 관리자 참고용 점검 리포트를 작성해줘.\n"
        "현재 고장 위험, 미래 10-step 이탈 예측, SHAP 요인을 함께 설명해줘.\n"
        "절대 자동 정비 명령처럼 쓰지 말고, 최종 조치는 현장 담당자가 확인해야 한다고 써줘.\n"
        "형식은 Markdown으로 하고, 1. 요약 2. 주요 근거 3. 관리자 참고 조치 4. 한계 순서로 써줘.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def extract_response_text(response_payload: dict) -> str:
    """Extract text from the OpenAI Responses API payload."""
    if response_payload.get("output_text"):
        return str(response_payload["output_text"]).strip()

    pieces = []
    for item in response_payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                pieces.append(text)
    return "\n".join(pieces).strip()


def extract_gemini_text(response_payload: dict) -> str:
    """Extract text from a Gemini generateContent response payload."""
    pieces = []
    for candidate in response_payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                pieces.append(text)
    return "\n".join(pieces).strip()


def ai_report_provider() -> str:
    """Return the selected GenAI report provider."""
    return (
        os.environ.get("AI_REPORT_PROVIDER", DEFAULT_AI_REPORT_PROVIDER)
        .strip()
        .lower()
        or DEFAULT_AI_REPORT_PROVIDER
    )


def openai_model_name() -> str:
    """Return the Responses API model, allowing a terminal-only override."""
    return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


def gemini_model_name() -> str:
    """Return the Gemini model, allowing a terminal-only override."""
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    if model.startswith("models/"):
        return model.removeprefix("models/")
    return model


def normalize_gemini_model_name(model: str) -> str:
    """Normalize a Gemini model id copied from docs or Google AI Studio."""
    model = model.strip()
    if model.startswith("models/"):
        return model.removeprefix("models/")
    return model


def gemini_model_candidates() -> list[str]:
    """Return Gemini models to try in order, with a low-latency fallback."""
    configured = os.environ.get("GEMINI_MODEL_CANDIDATES", "").strip()
    if configured:
        raw_models = configured.split(",")
    else:
        raw_models = [gemini_model_name(), *DEFAULT_GEMINI_FALLBACK_MODELS]

    candidates = []
    for raw_model in raw_models:
        model = normalize_gemini_model_name(raw_model)
        if model and model not in candidates:
            candidates.append(model)
    return candidates or [DEFAULT_GEMINI_MODEL]


def gemini_generate_content_url(model: str) -> str:
    """Build the Gemini generateContent URL for one model id."""
    encoded_model = urllib.parse.quote(model, safe="")
    return f"{GEMINI_GENERATE_CONTENT_BASE_URL}/{encoded_model}:generateContent"


def build_openai_headers(api_key: str) -> dict:
    """Build OpenAI headers without ever logging or persisting the API key."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    org_id = os.environ.get("OPENAI_ORG_ID", "").strip()
    project_id = os.environ.get("OPENAI_PROJECT_ID", "").strip()
    if org_id:
        headers["OpenAI-Organization"] = org_id
    if project_id:
        headers["OpenAI-Project"] = project_id
    return headers


def build_gemini_headers(api_key: str) -> dict:
    """Build Gemini headers without ever logging or persisting the API key."""
    return {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }


def build_openai_payload(input_text: str, max_output_tokens: int = 900) -> dict:
    """Create the official Responses API payload used by reports and preflight."""
    return {
        "model": openai_model_name(),
        "instructions": (
            "You write concise industrial engineering reports. Stay grounded in "
            "the provided evidence and include limitations."
        ),
        "input": input_text,
        "max_output_tokens": max_output_tokens,
        "truncation": "auto",
        "reasoning": {"effort": "low"},
    }


def build_gemini_payload(input_text: str, max_output_tokens: int = 900) -> dict:
    """Create the Gemini generateContent payload used by reports and preflight."""
    return {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "You write concise industrial engineering reports. "
                        "Stay grounded in the provided evidence and include limitations."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": input_text}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_output_tokens,
        },
    }


def format_openai_http_error(error: urllib.error.HTTPError) -> str:
    """Expose useful OpenAI error details while keeping credentials hidden."""
    body_text = ""
    try:
        body_text = error.read().decode("utf-8", errors="replace").strip()
    except OSError:
        body_text = ""

    request_id = ""
    if error.headers:
        request_id = error.headers.get("x-request-id", "") or error.headers.get("request-id", "")

    lines = [f"OpenAI API HTTP {error.code}: {error.reason}"]
    lines.append(f"x-request-id: {request_id or 'not provided'}")

    if not body_text:
        lines.append("response_body: empty")
        return "\n".join(lines)

    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        lines.append(f"response_body: {body_text[:2000]}")
        return "\n".join(lines)

    openai_error = payload.get("error", payload)
    if isinstance(openai_error, dict):
        message = openai_error.get("message")
        error_type = openai_error.get("type")
        error_code = openai_error.get("code")
        param = openai_error.get("param")
        if message:
            lines.append(f"error_message: {message}")
        if error_type:
            lines.append(f"error_type: {error_type}")
        if error_code:
            lines.append(f"error_code: {error_code}")
        if param:
            lines.append(f"error_param: {param}")
    else:
        lines.append(f"error: {openai_error}")

    return "\n".join(lines)


def format_gemini_http_error(error: urllib.error.HTTPError) -> str:
    """Expose useful Gemini error details while keeping credentials hidden."""
    body_text = ""
    try:
        body_text = error.read().decode("utf-8", errors="replace").strip()
    except OSError:
        body_text = ""

    lines = [f"Gemini API HTTP {error.code}: {error.reason}"]
    if not body_text:
        lines.append("response_body: empty")
        return "\n".join(lines)

    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        lines.append(f"response_body: {body_text[:2000]}")
        return "\n".join(lines)

    gemini_error = payload.get("error", payload)
    if isinstance(gemini_error, dict):
        message = gemini_error.get("message")
        status = gemini_error.get("status")
        code = gemini_error.get("code")
        if message:
            lines.append(f"error_message: {message}")
        if status:
            lines.append(f"error_status: {status}")
        if code:
            lines.append(f"error_code: {code}")
    else:
        lines.append(f"error: {gemini_error}")

    return "\n".join(lines)


def create_gemini_request(api_key: str, model: str, input_text: str, max_output_tokens: int) -> urllib.request.Request:
    """Create one Gemini generateContent request for the selected model."""
    payload = build_gemini_payload(input_text, max_output_tokens=max_output_tokens)
    return urllib.request.Request(
        gemini_generate_content_url(model),
        data=json.dumps(payload).encode("utf-8"),
        headers=build_gemini_headers(api_key),
        method="POST",
    )


def call_gemini_generate_content(
    api_key: str,
    input_text: str,
    max_output_tokens: int = 900,
    timeout: int = 45,
) -> tuple[str, str]:
    """Call Gemini, retrying transient overloads with fallback model candidates."""
    errors = []
    for model in gemini_model_candidates():
        for attempt in range(1, 3):
            request = create_gemini_request(api_key, model, input_text, max_output_tokens)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
                return extract_gemini_text(response_payload), model
            except urllib.error.HTTPError as error:
                error_detail = format_gemini_http_error(error)
                errors.append(f"model={model}, attempt={attempt}: {error_detail}")
                if error.code not in TRANSIENT_API_STATUS_CODES:
                    raise RuntimeError(error_detail) from error
                if attempt == 1:
                    time.sleep(2)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                error_detail = f"model={model}, attempt={attempt}: network_error: {error}"
                errors.append(error_detail)
                if attempt == 1:
                    time.sleep(2)

    raise RuntimeError(
        "Gemini API call failed for all model candidates.\n"
        + "\n\n".join(errors[-6:])
    )


def openai_ai_report(context: dict, require_openai: bool = False) -> tuple[str, str]:
    """
    Call the OpenAI Responses API when OPENAI_API_KEY is available.

    When require_openai is True, fallback is not accepted and API/key problems
    raise a clear error for the Stage 1~20 full verification run.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        if require_openai:
            raise RuntimeError(
                "OPENAI_API_KEY is required because REQUIRE_OPENAI_REPORT=1. "
                "Run run_stage1_20_openai.ps1 and enter a valid key."
            )
        return fallback_ai_report(context, "OPENAI_API_KEY not set"), "fallback_no_api_key"

    model = openai_model_name()
    payload = build_openai_payload(build_llm_prompt(context), max_output_tokens=900)
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=build_openai_headers(api_key),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        report = extract_response_text(response_payload)
        if not report:
            if require_openai:
                raise RuntimeError("OpenAI Responses API returned no report text.")
            return fallback_ai_report(context, "OpenAI response had no text"), "fallback_empty_response"
        return report, f"openai_responses_api:{model}"
    except urllib.error.HTTPError as error:
        error_detail = format_openai_http_error(error)
        if require_openai:
            raise RuntimeError(
                "OpenAI API call failed while require_openai=True.\n"
                f"{error_detail}"
            ) from error
        return fallback_ai_report(context, error_detail), "fallback_api_error"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        if require_openai:
            raise RuntimeError(f"OpenAI API call failed while require_openai=True: {error}") from error
        return fallback_ai_report(context, f"OpenAI API call failed: {error}"), "fallback_api_error"


def gemini_ai_report(context: dict, require_gemini: bool = False) -> tuple[str, str]:
    """
    Call the Gemini generateContent API when GEMINI_API_KEY is available.

    When require_gemini is True, fallback is not accepted for the Stage 1~20
    full verification run.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        if require_gemini:
            raise RuntimeError(
                "GEMINI_API_KEY is required because REQUIRE_GENAI_REPORT=1 "
                "and AI_REPORT_PROVIDER=gemini. Run run_stage1_20_gemini.ps1 "
                "and enter a valid key."
            )
        return fallback_ai_report(context, "GEMINI_API_KEY not set"), "fallback_no_api_key"

    try:
        report, model = call_gemini_generate_content(
            api_key,
            build_llm_prompt(context),
            max_output_tokens=900,
            timeout=45,
        )
        if not report:
            if require_gemini:
                raise RuntimeError("Gemini generateContent API returned no report text.")
            return fallback_ai_report(context, "Gemini response had no text"), "fallback_empty_response"
        return report, f"gemini_generate_content:{model}"
    except RuntimeError as error:
        if require_gemini:
            raise RuntimeError(f"Gemini API call failed while require_gemini=True: {error}") from error
        return fallback_ai_report(context, str(error)), "fallback_api_error"


def genai_ai_report(context: dict, require_genai: bool = False) -> tuple[str, str]:
    """Create the manager report with the selected GenAI provider."""
    provider = ai_report_provider()
    if provider == "gemini":
        return gemini_ai_report(context, require_gemini=require_genai)
    if provider == "openai":
        return openai_ai_report(context, require_openai=require_genai)

    message = (
        f"Unsupported AI_REPORT_PROVIDER: {provider}. "
        "Use 'gemini' or 'openai'."
    )
    if require_genai:
        raise RuntimeError(message)
    return fallback_ai_report(context, message), "fallback_api_error"


def save_ai_report(context: dict, report: str, mode: str) -> None:
    """Persist the report and add a small execution note."""
    context_with_mode = dict(context)
    context_with_mode["report_generation_mode"] = mode
    AI_CONTEXT_PATH.write_text(
        json.dumps(context_with_mode, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    AI_REPORT_PATH.write_text(report, encoding="utf-8")


def create_predictive_spc_outputs(
    require_genai: bool = False,
    require_openai: bool | None = None,
) -> dict:
    """Create SPC CSV, charts, summary JSON, and AI report draft artifacts."""
    if require_openai is not None:
        require_genai = require_openai

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions, raw_data, threshold_summary, local_case = load_inputs()
    selected_threshold = float(threshold_summary["selected_threshold"])

    spc_df = build_spc_timeseries(predictions, raw_data, selected_threshold)
    spc_summary = summarize_spc(spc_df, selected_threshold)
    spc_summary = add_future_deviation_summary(spc_summary)

    spc_df.to_csv(SPC_TIMESERIES_PATH, index=False, encoding="utf-8-sig")
    SPC_SUMMARY_PATH.write_text(
        json.dumps(spc_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_risk_chart(spc_df, SPC_RISK_CHART_PATH)
    save_control_chart(spc_df, SPC_CONTROL_CHART_PATH)

    context = build_ai_report_context(spc_df, spc_summary, local_case)
    report, mode = genai_ai_report(context, require_genai=require_genai)
    save_ai_report(context, report, mode)

    return {
        "spc_timeseries": str(SPC_TIMESERIES_PATH),
        "spc_summary": str(SPC_SUMMARY_PATH),
        "spc_risk_chart": str(SPC_RISK_CHART_PATH),
        "spc_control_chart": str(SPC_CONTROL_CHART_PATH),
        "ai_report_context": str(AI_CONTEXT_PATH),
        "ai_manager_report": str(AI_REPORT_PATH),
        "report_generation_mode": mode,
    }


def main() -> None:
    """Command-line entry point used by run_all.bat."""
    require_genai = (
        os.environ.get("REQUIRE_GENAI_REPORT", "").strip() == "1"
        or os.environ.get("REQUIRE_OPENAI_REPORT", "").strip() == "1"
    )
    outputs = create_predictive_spc_outputs(require_genai=require_genai)
    print("Predictive SPC and AI report outputs created successfully.")
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
