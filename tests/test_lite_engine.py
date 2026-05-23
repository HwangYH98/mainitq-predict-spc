from __future__ import annotations

from pathlib import Path

from desktop_app import lite_engine


def test_lite_engine_scores_sample_csv() -> None:
    result = lite_engine.predict_csv(lite_engine.lite_sample_csv_path())
    assert result["summary"]["row_count"] > 0
    assert "high_risk_count" in result["summary"]
    first = result["rows"][0]
    assert 0 <= float(first["failure_probability"]) <= 1
    assert "recommendation" in first


def test_lite_engine_saves_prediction_csv(tmp_path: Path) -> None:
    result = lite_engine.predict_csv(lite_engine.lite_sample_csv_path())
    target = tmp_path / "lite_predictions.csv"
    lite_engine.save_prediction_csv(result, target)
    assert target.exists()
    assert "failure_probability" in target.read_text(encoding="utf-8-sig")


def test_lite_provider_inference() -> None:
    assert lite_engine.infer_provider("AIza_example") == "gemini"
    assert lite_engine.infer_provider("sk-example") == "openai"
