from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _dashboard_functions() -> dict[str, str]:
    source = (ROOT / "app" / "dashboard.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    return {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def test_risk_monitoring_prefers_current_uploaded_prediction_result() -> None:
    functions = _dashboard_functions()
    monitor_source = functions["render_predictive_spc_tab"]

    assert 'st.session_state.get("smart_csv_prediction_result")' in monitor_source
    assert "render_uploaded_prediction_monitoring(uploaded_result)" in monitor_source
    assert "render_saved_spc_monitoring(spc_summary, spc_timeseries)" in monitor_source
    assert "저장된 SPC 기준 화면 보기" in monitor_source


def test_uploaded_monitoring_uses_prediction_contract_without_rerunning_experiments() -> None:
    functions = _dashboard_functions()
    upload_monitor_source = functions["render_uploaded_prediction_monitoring"]

    for required_contract in ["result_df", "priority_df", "raw_probability", "risk_status", "recommendation"]:
        assert required_contract in upload_monitor_source
    assert "prepare_work_order_from_monitoring_row" in upload_monitor_source
    assert "작업지시 후보 연결" in upload_monitor_source

    forbidden_terms = [
        "predict_company_sensor_csv(",
        "predict_scania_csv(",
        "reproduce_all.ps1",
        "subprocess",
        "os.system",
    ]
    found = [term for term in forbidden_terms if term in upload_monitor_source]
    assert not found


def test_operator_app_shows_workflow_status_without_mixing_admin_research() -> None:
    functions = _dashboard_functions()
    user_source = functions["render_user_app"]

    assert "render_operator_workflow_status()" in user_source
    assert "render_research_validation_tab()" not in user_source
    assert "render_research_validation_tab()" in functions["render_admin_app"]


def test_prediction_tab_uses_operator_error_format_and_grouped_downloads() -> None:
    functions = _dashboard_functions()
    prediction_source = functions["render_field_csv_tab"]

    assert "show_operator_error(" in prediction_source
    assert "문제:" not in prediction_source  # wording lives in the shared helper
    assert "상단의 <strong>위험 모니터링</strong> 탭" in prediction_source
    assert "#### 다운로드" in prediction_source
    assert "예측 결과 CSV" in prediction_source
    assert "위험 우선순위 CSV" in prediction_source


def test_report_and_work_order_errors_use_operator_error_format() -> None:
    functions = _dashboard_functions()

    assert "show_operator_error(" in functions["render_ai_report_tab"]
    assert "리포트 파일" in functions["render_ai_report_tab"]
    assert "show_operator_error(" in functions["render_stage19_20_input_controls"]
    assert "operations_prefill_message" in functions["render_stage19_20_input_controls"]
    assert "stage20_prefilled_event_id" in functions["render_stage19_20_input_controls"]
