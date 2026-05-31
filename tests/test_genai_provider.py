from __future__ import annotations

import pytest

from desktop_app.genai import infer_provider_from_key, model_candidates_for
from predictive_spc import build_gemini_payload


def test_infer_provider_from_key() -> None:
    assert infer_provider_from_key("AIza-example") == "gemini"
    assert infer_provider_from_key("sk-example") == "openai"


def test_infer_provider_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):
        infer_provider_from_key("not-a-supported-key")


def test_model_candidates_have_standard_and_advanced_modes() -> None:
    assert model_candidates_for("gemini", "standard")
    assert model_candidates_for("gemini", "advanced")
    assert model_candidates_for("openai", "standard")
    assert model_candidates_for("openai", "advanced")


def test_gemini_advanced_mode_requires_latest_flash() -> None:
    assert model_candidates_for("gemini", "advanced") == ["gemini-3.5-flash"]
    assert "gemini-2.5-flash" in model_candidates_for("gemini", "standard")
    assert "gemini-2.5-flash" not in model_candidates_for("gemini", "advanced")


def test_gemini_payload_uses_v1_field_names() -> None:
    payload = build_gemini_payload("hello", max_output_tokens=32)

    assert "systemInstruction" not in payload
    assert "system_instruction" not in payload
    assert "System instruction:" in payload["contents"][0]["parts"][0]["text"]
    assert payload["generationConfig"]["maxOutputTokens"] == 32
