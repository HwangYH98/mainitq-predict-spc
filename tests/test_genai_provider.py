from __future__ import annotations

import pytest

from desktop_app.genai import infer_provider_from_key, model_candidates_for


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
