import json
import os
import urllib.error
import urllib.request

from predictive_spc import (
    OPENAI_RESPONSES_URL,
    build_openai_headers,
    build_openai_payload,
    extract_response_text,
    format_openai_http_error,
    openai_model_name,
)


def main() -> None:
    """Run a tiny Responses API request before the long Stage 1~20 pipeline."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY is missing. Run run_stage1_20_openai.ps1 and enter "
            "a valid key, or set OPENAI_API_KEY only for the current terminal."
        )

    payload = build_openai_payload(
        "Reply with exactly this short phrase: OpenAI preflight ok",
        max_output_tokens=64,
    )
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=build_openai_headers(api_key),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit(
            "OpenAI preflight failed before the long pipeline started.\n"
            f"{format_openai_http_error(error)}"
        ) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise SystemExit(
            "OpenAI preflight failed before the long pipeline started.\n"
            f"network_error: {error}"
        ) from error

    text = extract_response_text(response_payload)
    if not text:
        raise SystemExit(
            "OpenAI preflight failed: Responses API returned no text."
        )

    print("OpenAI preflight succeeded.")
    print(f"model: {openai_model_name()}")
    print(f"response_preview: {text[:120]}")


if __name__ == "__main__":
    main()
