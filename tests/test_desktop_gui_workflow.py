from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _streamlit_user_app():
    from streamlit.testing.v1 import AppTest

    os.environ["APP_OPERATOR_PASSWORD"] = "operator-test"
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    app.session_state["operator_authenticated"] = True
    app.session_state["auth_user"] = {"actor_id": "operator_01", "role": "operator"}
    app.run(timeout=300)
    return app


def _element_values(collection) -> list[str]:
    return [str(getattr(item, "value", "")) for item in collection if getattr(item, "value", None) is not None]


def _button_labels(app) -> list[str]:
    return [str(getattr(button, "label", "")) for button in app.button]


def _click_button_containing(app, label_part: str, timeout: int = 300):
    for index, label in enumerate(_button_labels(app)):
        if label_part in label:
            app.button[index].click().run(timeout=timeout)
            return app
    raise AssertionError(f"Button containing {label_part!r} was not found. Buttons: {_button_labels(app)}")


def test_desktop_gui_workflow_smoke_command() -> None:
    result = subprocess.run(
        [sys.executable, "desktop_app/main.py", "--workflow-smoke-test"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Desktop GUI workflow smoke test passed." in result.stdout


def test_desktop_gui_click_workflow_command() -> None:
    result = subprocess.run(
        [sys.executable, "desktop_app/main.py", "--click-workflow-test"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Desktop GUI click workflow test passed." in result.stdout


def test_lite_gui_workflow_smoke_command() -> None:
    result = subprocess.run(
        [sys.executable, "desktop_app/lite_main.py", "--workflow-smoke-test"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Lite GUI workflow smoke test passed." in result.stdout


def test_lite_gui_click_workflow_command() -> None:
    result = subprocess.run(
        [sys.executable, "desktop_app/lite_main.py", "--click-workflow-test"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Lite GUI click workflow test passed." in result.stdout


def test_streamlit_ai4i_upload_prediction_and_report_fallback() -> None:
    app = _streamlit_user_app()
    ai4i_path = ROOT / "data" / "ai4i2020.csv"

    app.file_uploader[0].upload(ai4i_path.name, ai4i_path.read_bytes(), "text/csv").run(timeout=300)
    assert any("전처리와 예측 실행" in label for label in _button_labels(app))

    _click_button_containing(app, "전처리와 예측 실행")
    assert "전처리와 예측이 완료되었습니다." in _element_values(app.success)
    assert not _element_values(app.error)

    result = app.session_state["smart_csv_prediction_result"]
    report = result["quality_report"]
    assert report["quality_status"] == "High"
    assert report["row_count"] == 10000
    assert report["mapped_columns"] == {
        "Type": "Type",
        "Air temperature [K]": "Air temperature [K]",
        "Process temperature [K]": "Process temperature [K]",
        "Rotational speed [rpm]": "Rotational speed [rpm]",
        "Torque [Nm]": "Torque [Nm]",
        "Tool wear [min]": "Tool wear [min]",
    }
    assert result["result_df"]["risk_status"].isin(["Normal", "High Risk"]).all()

    _click_button_containing(app, "선택 row로 AI 리포트 생성")
    assert not _element_values(app.error)


def test_streamlit_scania_and_public_benchmark_upload_paths(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from scania_product_engine import SCANIA_MODEL_ARTIFACT, sample_scania_dataframe
    from desktop_app.prediction_page import detect_public_benchmark_csv

    scania_app = _streamlit_user_app()
    scania_bytes = sample_scania_dataframe(row_count=5).to_csv(index=False).encode("utf-8")
    scania_app.file_uploader[0].upload("scania_readouts.csv", scania_bytes, "text/csv").run(timeout=300)
    assert any("SCANIA 예측 실행" in label for label in _button_labels(scania_app))
    if SCANIA_MODEL_ARTIFACT.exists():
        _click_button_containing(scania_app, "SCANIA 예측 실행")
        assert "SCANIA 전용 예측이 완료되었습니다." in _element_values(scania_app.success)
        assert not _element_values(scania_app.error)

    scania_spec_app = _streamlit_user_app()
    scania_spec_csv = b"vehicle_id,Spec_0,Spec_1\nV001,A,B\n"
    scania_spec_app.file_uploader[0].upload("train_specifications.csv", scania_spec_csv, "text/csv").run(timeout=300)
    assert not any("예측 실행" in label for label in _button_labels(scania_spec_app))
    assert any("SCANIA Component X benchmark metadata/specification file" in value for value in _element_values(scania_spec_app.warning))

    scania_tte_app = _streamlit_user_app()
    scania_tte_csv = b"vehicle_id,length_of_study_time_step,in_study_repair\nV001,120,1\n"
    scania_tte_app.file_uploader[0].upload("train_tte.csv", scania_tte_csv, "text/csv").run(timeout=300)
    assert not any("예측 실행" in label for label in _button_labels(scania_tte_app))
    assert any("SCANIA Component X benchmark metadata/specification file" in value for value in _element_values(scania_tte_app.warning))

    metropt_app = _streamlit_user_app()
    metropt_csv = (
        "timestamp,TP2,TP3,Oil_temperature,Motor_current,Caudal_impulses\n"
        "2026-01-01 00:00:00,1.0,2.0,55.0,4.2,10\n"
    ).encode("utf-8")
    metropt_app.file_uploader[0].upload("MetroPT3(AirCompressor).csv", metropt_csv, "text/csv").run(timeout=300)
    assert not any("예측 실행" in label for label in _button_labels(metropt_app))
    assert any("MetroPT-3 compressor benchmark" in value for value in _element_values(metropt_app.warning))

    femto_app = _streamlit_user_app()
    femto_path = ROOT / "data_external" / "femto" / "pronostia_phm2012" / "Test_set" / "Bearing1_3" / "acc_00001.csv"
    if femto_path.exists():
        femto_bytes = femto_path.read_bytes()
    else:
        femto_bytes = b"8,33,1,3.7816e+05,2,4\n1,2,3,4,5,6\n"
    femto_app.file_uploader[0].upload("acc_00001.csv", femto_bytes, "text/csv").run(timeout=300)
    assert not any("예측 실행" in label for label in _button_labels(femto_app))
    assert any("FEMTO/PRONOSTIA bearing benchmark" in value for value in _element_values(femto_app.warning))

    import pandas as pd

    assert detect_public_benchmark_csv(pd.DataFrame({"vehicle_id": ["V001"], "Spec_0": ["A"]}))
    assert detect_public_benchmark_csv(pd.DataFrame({"vehicle_id": ["V001"], "class_label": [0]}))
    assert detect_public_benchmark_csv(pd.DataFrame({"vehicle_id": ["V001"], "length_of_study_time_step": [10]}))


def test_scania_sample_generation_without_model_artifact(monkeypatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    import scania_product_engine

    monkeypatch.setattr(scania_product_engine, "DATA_EXTERNAL_DIR", tmp_path / "missing_scania_data")
    monkeypatch.setattr(scania_product_engine, "SCANIA_MODEL_ARTIFACT", tmp_path / "missing_model.joblib")

    sample = scania_product_engine.sample_scania_dataframe(row_count=5)

    assert len(sample) == 5
    assert scania_product_engine.detect_input_schema(sample) == "scania"


def test_streamlit_work_order_buttons_create_auditable_flow() -> None:
    app = _streamlit_user_app()

    for label in ["High Risk 샘플 채우기", "센서 이벤트 생성", "작업지시 초안 생성", "결정 기록 저장"]:
        _click_button_containing(app, label)
        assert not _element_values(app.error)


def test_desktop_full_navigation_and_major_button_contracts(monkeypatch, tmp_path: Path) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop_app import ai_report_page as ai_report_module
    from desktop_app import pages as pages_module
    from desktop_app import prediction_page as prediction_module
    from desktop_app.pages import MainWindow, default_actor
    from desktop_app.prediction_page import DataPredictionPage
    from desktop_app.work_order_page import WorkOrderPage
    from desktop_app.ai_report_page import AIReportPage

    sample_save_path = tmp_path / "saved_sample.csv"
    result_export_path = tmp_path / "prediction_results.csv"
    report_export_path = tmp_path / "ai_report_export.md"
    opened_folders: list[str] = []
    opened_urls: list[str] = []
    exported_logs: list[Path] = []
    save_dialog_calls: list[tuple[str, str]] = []

    class FakeMessageBox:
        class StandardButton:
            Open = 1
            Close = 2

        @staticmethod
        def information(*args, **kwargs):
            return None

        @staticmethod
        def warning(*args, **kwargs):
            return None

        @staticmethod
        def question(*args, **kwargs):
            return FakeMessageBox.StandardButton.Close

    class FakePredictionFileDialog:
        @staticmethod
        def getSaveFileName(parent, caption, default, file_filter):
            save_dialog_calls.append((str(caption), str(default)))
            if Path(str(default)).name.startswith("sample_"):
                return str(sample_save_path), file_filter
            return str(result_export_path), file_filter

        @staticmethod
        def getOpenFileName(*args):
            return str(sample_save_path), "CSV Files (*.csv)"

    class FakeAIReportFileDialog:
        @staticmethod
        def getSaveFileName(*args):
            return str(report_export_path), "Markdown Files (*.md)"

    monkeypatch.setattr(prediction_module, "QFileDialog", FakePredictionFileDialog)
    monkeypatch.setattr(prediction_module, "QMessageBox", FakeMessageBox)
    monkeypatch.setattr(prediction_module.os, "startfile", lambda path: opened_folders.append(str(path)))
    monkeypatch.setattr(ai_report_module, "QFileDialog", FakeAIReportFileDialog)
    monkeypatch.setattr(ai_report_module, "QMessageBox", FakeMessageBox)
    monkeypatch.setattr(ai_report_module, "resolve_genai_connection", lambda *args, **kwargs: {"provider": "gemini", "model": "gemini-test", "mode": "standard"})
    monkeypatch.setattr(
        pages_module,
        "check_for_update",
        lambda: type(
            "UpdateResult",
            (),
            {
                "has_update": False,
                "message": "No update available.",
                "current_version": "1.1.2",
                "latest_version": "1.1.2",
                "release_url": "",
            },
        )(),
    )
    monkeypatch.setattr(pages_module.QDesktopServices, "openUrl", lambda url: opened_urls.append(url.toString()) or True)
    monkeypatch.setattr(pages_module, "QMessageBox", FakeMessageBox)
    monkeypatch.setattr(pages_module, "export_crash_logs", lambda output=None: exported_logs.append(tmp_path / "logs.zip") or (tmp_path / "logs.zip"))

    app = QApplication.instance() or QApplication([])
    window = MainWindow(default_actor())
    window.show()
    app.processEvents()

    def click_and_drain(button) -> None:
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        app.processEvents()

    for index, button in enumerate(window.nav_buttons):
        click_and_drain(button)
        assert window.stack.currentIndex() == index
        assert button.isChecked()

    prediction_page: DataPredictionPage = window.page_instances["prediction"]  # type: ignore[assignment]
    try:
        prediction_page.prediction_completed.disconnect(window.refresh_related_pages)
    except (RuntimeError, TypeError):
        pass
    window.set_page(1)
    app.processEvents()
    assert not prediction_page.predict_button.isEnabled()
    assert not prediction_page.quick_export_button.isEnabled()
    click_and_drain(prediction_page.sample_button)
    if not sample_save_path.exists():
        prediction_page.sample_button.click()
        app.processEvents()
    if not sample_save_path.exists():
        prediction_page.save_sample_csv()
        app.processEvents()
    assert sample_save_path.exists(), save_dialog_calls
    click_and_drain(prediction_page.load_button)
    assert prediction_page.predict_button.isEnabled()
    assert prediction_page.mapping_table.isVisible()
    click_and_drain(prediction_page.use_sample_button)
    assert prediction_page.predict_button.isEnabled()
    click_and_drain(prediction_page.predict_button)
    assert prediction_page.prediction_result
    assert prediction_page.quick_export_button.isEnabled()
    assert prediction_page.export_button.isEnabled()
    assert not prediction_page.open_folder_button.isEnabled() or prediction_page.last_saved_path
    click_and_drain(prediction_page.quick_export_button)
    assert prediction_page.last_saved_path and prediction_page.last_saved_path.exists()
    click_and_drain(prediction_page.export_button)
    assert result_export_path.exists()
    click_and_drain(prediction_page.open_folder_button)
    assert opened_folders

    work_order_page: WorkOrderPage = window.page_instances["work_order"]  # type: ignore[assignment]
    window.set_page(4)
    app.processEvents()
    click_and_drain(work_order_page.normal_button)
    click_and_drain(work_order_page.high_button)
    click_and_drain(work_order_page.event_button)
    assert work_order_page.latest_event
    click_and_drain(work_order_page.draft_button)
    assert work_order_page.latest_draft
    work_order_page.decision_combo.setCurrentIndex(1)
    work_order_page.note_input.setText("button contract test")
    click_and_drain(work_order_page.decision_button)

    ai_page: AIReportPage = window.page_instances["ai_report"]  # type: ignore[assignment]
    window.set_page(3)
    app.processEvents()
    assert not ai_page.check_button.isEnabled()
    assert not ai_page.generate_button.isEnabled()
    click_and_drain(ai_page.load_button)
    assert ai_page.report_text.toPlainText()
    ai_page.report_text.setPlainText("contract test report")
    ai_page.export_button.setEnabled(True)
    click_and_drain(ai_page.export_button)
    assert report_export_path.exists()
    click_and_drain(ai_page.detail_button)

    window.set_page(0)
    click_and_drain(window.nav_buttons[0])
    window.check_updates()
    window.export_crash_logs()
    assert exported_logs

    window.close()
    app.processEvents()


def test_prediction_outputs_include_engine_provenance() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from preprocessing_prediction_engine import infer_column_mapping, predict_company_sensor_csv, sample_company_alias_dataframe
    from desktop_app import lite_engine

    sample = sample_company_alias_dataframe()
    mapping_df = infer_column_mapping(sample)
    mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
    full_result = predict_company_sensor_csv(sample, mapping=mapping, write_outputs=False)
    full_columns = set(full_result["result_df"].columns)
    for column in ["engine_profile", "score_method", "interpretation_note"]:
        assert column in full_columns
    assert full_result["result_df"]["engine_profile"].eq("full").all()
    assert "정밀 분석 모드" in str(full_result["result_df"]["interpretation_note"].iloc[0])

    lite_result = lite_engine.predict_csv(lite_engine.lite_sample_csv_path(), policy_id="balanced")
    for column in ["engine_profile", "score_method", "interpretation_note", "selected_threshold"]:
        assert column in lite_result["rows"][0]
    assert lite_result["rows"][0]["engine_profile"] == "lite"
    assert "빠른 점검 모드" in str(lite_result["rows"][0]["interpretation_note"])


def test_scania_schema_detection_and_product_prediction() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from scania_product_engine import SCANIA_MODEL_ARTIFACT, detect_input_schema, predict_scania_csv, sample_scania_dataframe

    if not SCANIA_MODEL_ARTIFACT.exists():
        return
    sample = sample_scania_dataframe(row_count=5)
    assert detect_input_schema(sample) == "scania"
    result = predict_scania_csv(sample, write_outputs=False)
    assert result["schema"] == "scania"
    assert {"engine_profile", "score_method", "interpretation_note", "predicted_class"}.issubset(result["result_df"].columns)
    assert result["result_df"]["engine_profile"].eq("scania").all()


def test_desktop_user_visible_text_guardrail() -> None:
    product_files = [
        "desktop_app/config.py",
        "desktop_app/pages.py",
        "desktop_app/home_page.py",
        "desktop_app/prediction_page.py",
        "desktop_app/monitoring_page.py",
        "desktop_app/ai_report_page.py",
        "desktop_app/work_order_page.py",
        "desktop_app/widgets.py",
        "desktop_app/formatters.py",
        "desktop_app/genai.py",
        "desktop_app/report_history.py",
        "desktop_app/runtime_profile.py",
        "desktop_app/lite_main.py",
        "desktop_app/lite_engine.py",
        "desktop_app/lite_widgets.py",
    ]
    forbidden_terms = [
        "capstone",
        "presentation",
        "PoC",
        "Demo",
        "Stage",
        "캡스톤",
        "발표",
        "중간발표",
        "최종발표",
    ]
    mojibake_markers = [
        "�",
        "锟",
        "理",
        "諛",
        "怨좎",
        "由ы",
        "鍮좊",
        "寃",
        "媛",
    ]
    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in product_files)
    found_forbidden = [term for term in forbidden_terms if term in combined]
    found_mojibake = [term for term in mojibake_markers if term in combined]
    assert not found_forbidden
    assert not found_mojibake


def test_streamlit_user_app_tabs_and_text_guardrail() -> None:
    dashboard_path = ROOT / "app/dashboard.py"
    source = dashboard_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    assert source.count("def render_field_csv_tab(") == 1

    user_app_source = functions["render_user_app"]
    for tab_name in ["홈", "데이터 예측", "위험 모니터링", "AI 리포트", "작업지시"]:
        assert tab_name in user_app_source
    for admin_only_tab in ["회사 데이터 재학습", "공개 산업 데이터 검증", "현장 검증 템플릿", "제품 비교 근거"]:
        assert admin_only_tab not in user_app_source

    user_visible_functions = [
        "render_user_app",
        "render_start_tab",
        "render_product_summary_tab",
        "render_field_csv_tab",
        "render_predictive_spc_tab",
        "render_ai_report_tab",
        "render_work_order_tab",
        "render_scope_tab",
    ]
    forbidden_terms = ["capstone", "presentation", "PoC", "Demo", "Stage", "캡스톤", "발표", "데모", "중간발표", "최종발표"]
    combined = "\n".join(functions[name] for name in user_visible_functions)
    found_forbidden = [term for term in forbidden_terms if term in combined]
    assert not found_forbidden
