from __future__ import annotations

import io
import json
import urllib.error

from desktop_app.update_checker import check_for_update, is_newer_version


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_version_comparison() -> None:
    assert is_newer_version("v1.2.0", "1.1.9")
    assert is_newer_version("1.1.2", "1.1.1")
    assert not is_newer_version("v1.1.1", "1.1.1")
    assert not is_newer_version("1.0.9", "1.1.1")


def test_update_available_from_github_release_payload() -> None:
    def opener(request, timeout=8):  # noqa: ARG001
        return FakeResponse({"tag_name": "v9.9.9", "html_url": "https://example.test/release"})

    result = check_for_update(repository="owner/repo", current_version="1.1.1", opener=opener)
    assert result.status == "update_available"
    assert result.has_update
    assert result.latest_version == "v9.9.9"
    assert result.release_url == "https://example.test/release"


def test_update_checker_handles_private_or_unavailable_release() -> None:
    def opener(request, timeout=8):  # noqa: ARG001
        raise urllib.error.HTTPError(
            url="https://api.github.com/repos/owner/repo/releases/latest",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b"{}"),
        )

    result = check_for_update(repository="owner/repo", current_version="1.1.1", opener=opener)
    assert result.status == "unavailable"
    assert not result.has_update
    assert "HTTP 404" in result.message
