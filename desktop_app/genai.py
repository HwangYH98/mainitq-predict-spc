from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from desktop_app.config import (
    GEMINI_ADVANCED_MODELS,
    GEMINI_STANDARD_MODELS,
    OPENAI_ADVANCED_MODELS,
    OPENAI_STANDARD_MODELS,
)


def infer_provider_from_key(api_key: str) -> str:
    key = api_key.strip()
    if key.startswith("AIza"):
        return "gemini"
    if key.startswith("sk-"):
        return "openai"
    raise ValueError("API key 형식을 인식하지 못했습니다. Gemini 또는 OpenAI API key를 입력하세요.")


def model_candidates_for(provider: str, mode: str) -> list[str]:
    if provider == "gemini":
        return GEMINI_ADVANCED_MODELS if mode == "advanced" else GEMINI_STANDARD_MODELS
    if provider == "openai":
        return OPENAI_ADVANCED_MODELS if mode == "advanced" else OPENAI_STANDARD_MODELS
    raise ValueError(f"지원하지 않는 AI 제공자입니다: {provider}")


def provider_label(provider: str) -> str:
    return "Gemini" if provider == "gemini" else "OpenAI"


def mode_label(mode: str) -> str:
    return "고성능 모드" if mode == "advanced" else "표준 모드"


def with_restored_env(names: list[str]) -> dict[str, str | None]:
    """Capture environment values so API keys never stay in the process longer than needed."""
    return {name: os.environ.get(name) for name in names}


def restore_env(saved: dict[str, str | None]) -> None:
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def resolve_genai_connection(api_key: str, mode: str, prompt: str = "Reply with: ok") -> dict:
    """
    Try provider/model candidates and return the first working API connection.

    Provider is inferred from the key prefix, while paid/free availability is
    determined by real preflight success instead of guessing account billing.
    """
    provider = infer_provider_from_key(api_key)
    candidates = model_candidates_for(provider, mode)
    old_env = with_restored_env(
        [
            "AI_REPORT_PROVIDER",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_MODEL",
            "OPENAI_MODEL",
            "GEMINI_MODEL_CANDIDATES",
        ]
    )
    errors: list[str] = []
    try:
        os.environ["AI_REPORT_PROVIDER"] = provider
        if provider == "gemini":
            from predictive_spc import call_gemini_generate_content

            os.environ["GEMINI_API_KEY"] = api_key
            for model in candidates:
                try:
                    os.environ["GEMINI_MODEL_CANDIDATES"] = model
                    text, resolved_model = call_gemini_generate_content(
                        api_key,
                        prompt,
                        max_output_tokens=40,
                        timeout=20,
                    )
                    if text.strip():
                        return {"provider": provider, "model": resolved_model, "mode": mode}
                except Exception as error:
                    errors.append(f"{model}: {error}")
        else:
            from predictive_spc import (
                OPENAI_RESPONSES_URL,
                build_openai_headers,
                build_openai_payload,
                extract_response_text,
                format_openai_http_error,
            )

            os.environ["OPENAI_API_KEY"] = api_key
            for model in candidates:
                try:
                    os.environ["OPENAI_MODEL"] = model
                    payload = build_openai_payload(prompt, max_output_tokens=40)
                    request = urllib.request.Request(
                        OPENAI_RESPONSES_URL,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=build_openai_headers(api_key),
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=20) as response:
                        response_payload = json.loads(response.read().decode("utf-8"))
                    if extract_response_text(response_payload).strip():
                        return {"provider": provider, "model": model, "mode": mode}
                except urllib.error.HTTPError as error:
                    errors.append(f"{model}: {format_openai_http_error(error)}")
                except Exception as error:
                    errors.append(f"{model}: {error}")
    finally:
        restore_env(old_env)

    detail = "\n".join(errors[-4:]) if errors else "연결 가능한 모델을 찾지 못했습니다."
    raise RuntimeError(f"{provider_label(provider)} {mode_label(mode)} 연결 확인에 실패했습니다.\n{detail}")
