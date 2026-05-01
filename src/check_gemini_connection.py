import os

from predictive_spc import (
    call_gemini_generate_content,
    gemini_model_candidates,
)


def main() -> None:
    """Run a tiny Gemini generateContent request before the long pipeline."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY is missing. Run run_stage1_20_gemini.ps1 and enter "
            "a valid Google AI Studio key, or set GEMINI_API_KEY only for the "
            "current terminal."
        )

    try:
        text, model = call_gemini_generate_content(
            api_key,
            "Reply with exactly this short phrase: Gemini preflight ok",
            max_output_tokens=64,
            timeout=30,
        )
    except RuntimeError as error:
        raise SystemExit(
            "Gemini preflight failed before the long pipeline started.\n"
            f"{error}"
        ) from error

    if not text:
        raise SystemExit(
            "Gemini preflight failed: generateContent API returned no text."
        )

    print("Gemini preflight succeeded.")
    print(f"model: {model}")
    print(f"model_candidates: {', '.join(gemini_model_candidates())}")
    print(f"response_preview: {text[:120]}")


if __name__ == "__main__":
    main()
