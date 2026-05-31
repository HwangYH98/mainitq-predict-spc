from __future__ import annotations

from desktop_app.version import APP_VERSION


PRODUCT_NAME = "MaintiQ Predict"
PRODUCT_SUBTITLE = "AI 예지보전 운영 워크스테이션"
PRODUCT_WINDOW_TITLE = f"MaintiQ Predict {APP_VERSION}"

GEMINI_STANDARD_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
GEMINI_ADVANCED_MODELS = ["gemini-3.5-flash"]
OPENAI_STANDARD_MODELS = [
    "gpt-5.2",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1-mini",
    "gpt-4o-mini",
]
OPENAI_ADVANCED_MODELS = [
    "gpt-5.2-pro",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5-pro",
    "gpt-5",
    "gpt-5-mini",
    "gpt-4.1",
]


DISPLAY_COLUMN_NAMES = {
    "time_step": "시점",
    "simulated_timestamp": "시각",
    "input_row": "입력 행",
    "priority_rank": "우선순위",
    "vehicle_id": "차량 ID",
    "Type": "제품 등급",
    "Air temperature [K]": "공기 온도 [K]",
    "Process temperature [K]": "공정 온도 [K]",
    "Rotational speed [rpm]": "회전 속도 [rpm]",
    "Torque [Nm]": "토크 [Nm]",
    "Tool wear [min]": "공구 마모 [min]",
    "xgboost_probability": "고장 확률",
    "raw_probability": "원 확률",
    "calibrated_probability": "보정 확률",
    "failure_window_probability": "고장 window 확률",
    "predicted_class": "예측 class",
    "argmax_class": "최대확률 class",
    "class_meaning": "class 의미",
    "expected_cost_min": "예상 비용",
    "selected_threshold": "판정 기준",
    "risk_status": "위험 상태",
    "risk_priority_score": "위험 우선순위 점수",
    "data_quality_status": "데이터 품질",
    "recommendation": "권장 조치",
    "created_at": "생성 시각",
    "event_id": "센서 이벤트",
    "draft_id": "작업지시 초안",
    "decision_id": "결정 이력",
    "probability": "고장 확률",
    "threshold": "판정 기준",
    "source": "입력 출처",
    "generation_mode": "생성 방식",
    "operator_id": "작업자",
    "decision": "작업자 결정",
    "note": "메모",
    "engine_profile": "엔진 구분",
    "score_method": "계산 방식",
    "interpretation_note": "해석 안내",
}
