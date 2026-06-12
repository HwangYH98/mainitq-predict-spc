from __future__ import annotations

import json
import os
from pathlib import Path

import genai_evaluation
from genai_evaluation import load_cases, run_evaluation


def test_load_cases_meets_preregistered_case_mix() -> None:
    cases = load_cases()
    counts: dict[str, int] = {}
    for case in cases:
        counts[case["risk_level"]] = counts.get(case["risk_level"], 0) + 1

    assert counts["low"] >= 5
    assert counts["boundary"] >= 5
    assert counts["high"] >= 5
    assert counts["incomplete"] >= 3


def test_offline_evaluation_calls_existing_generator_without_api_keys(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-value")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-value")

    def fake_genai_ai_report(context: dict, require_genai: bool = False) -> tuple[str, str]:
        assert require_genai is False
        assert "GEMINI_API_KEY" not in os.environ
        assert "OPENAI_API_KEY" not in os.environ
        calls.append(context["row"]["UDI"])
        shap = ", ".join(item["feature"] for item in context.get("top_shap_factors", []))
        if not shap:
            shap = "SHAP factors unavailable"
        response = (
            f"Probability is {context['row']['xgboost_probability']:.4f} and threshold "
            f"{context['row']['selected_threshold']:.2f}. Evidence uses {shap}. "
            "Sensors reviewed: Air temperature [K], Process temperature [K], "
            "Rotational speed [rpm], Torque [Nm], Tool wear [min]. "
            "This is not an automatic maintenance order. Human approval is required; "
            "confirmed action must be approved by field staff. Boundary uncertainty "
            "or incomplete input requires review."
        )
        return response, "test_offline_generator"

    monkeypatch.setattr(genai_evaluation, "genai_ai_report", fake_genai_ai_report)

    run_dir = run_evaluation(
        run_id="genai-test-run",
        experiment_root=tmp_path,
        repetitions=1,
        offline_replay=True,
    )

    cases = load_cases()
    raw_path = run_dir / "raw_responses" / "genai_raw_responses.jsonl"
    check_path = run_dir / "checks" / "genai_automatic_checks.csv"
    human_form_path = run_dir / "review" / "genai_human_review_form.csv"
    verification_path = run_dir / "verification_report.json"

    raw_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    verification = json.loads(verification_path.read_text(encoding="utf-8"))

    assert len(calls) == len(cases) * 2
    assert len(raw_rows) == len(cases) * 2
    assert check_path.exists()
    assert human_form_path.exists()
    assert "factual_consistency_1_to_5" in human_form_path.read_text(encoding="utf-8-sig")
    assert verification["summary"]["case_count"] == len(cases)
    assert verification["summary"]["preregistered_targets"]["autonomous_command_count"] == 0


def test_run_evaluation_refuses_non_empty_existing_run_dir(tmp_path) -> None:
    run_dir = tmp_path / "existing-run"
    run_dir.mkdir()
    (run_dir / "marker.txt").write_text("do not overwrite", encoding="utf-8")

    try:
        run_evaluation(run_id="existing-run", experiment_root=tmp_path, repetitions=0)
    except FileExistsError as error:
        assert "Refusing to reuse" in str(error)
    else:
        raise AssertionError("run_evaluation reused a non-empty run directory")
