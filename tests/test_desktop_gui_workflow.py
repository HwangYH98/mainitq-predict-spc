from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


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
