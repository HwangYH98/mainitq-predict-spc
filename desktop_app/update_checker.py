from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import urllib.error
import urllib.request

from desktop_app.version import APP_VERSION


DEFAULT_RELEASE_REPOSITORY = "HwangYH98/capstone-design-ai4i-genai-spc"


@dataclass(frozen=True)
class UpdateCheckResult:
    status: str
    current_version: str
    latest_version: str | None = None
    release_url: str | None = None
    message: str = ""

    @property
    def has_update(self) -> bool:
        return self.status == "update_available"


def normalize_version(value: str) -> tuple[int, ...]:
    """Convert v1.2.3 or 1.2.3-beta into a comparable numeric tuple."""
    cleaned = value.strip().lower().removeprefix("v")
    parts = re.split(r"[^0-9]+", cleaned)
    numbers = [int(part) for part in parts if part.isdigit()]
    return tuple(numbers or [0])


def is_newer_version(latest: str, current: str) -> bool:
    latest_parts = list(normalize_version(latest))
    current_parts = list(normalize_version(current))
    width = max(len(latest_parts), len(current_parts))
    latest_parts.extend([0] * (width - len(latest_parts)))
    current_parts.extend([0] * (width - len(current_parts)))
    return tuple(latest_parts) > tuple(current_parts)


def github_release_api_url(repository: str) -> str:
    return f"https://api.github.com/repos/{repository}/releases/latest"


def github_release_page_url(repository: str) -> str:
    return f"https://github.com/{repository}/releases/latest"


def check_for_update(
    repository: str | None = None,
    current_version: str = APP_VERSION,
    timeout: int = 8,
    opener=urllib.request.urlopen,
) -> UpdateCheckResult:
    """Check GitHub Releases and return an operator-facing update status.

    Private repositories may return 404 without a token. In that case the app
    reports that release information is unavailable instead of failing the UI.
    """
    repository = repository or os.environ.get("MAINTIQ_UPDATE_REPO", DEFAULT_RELEASE_REPOSITORY)
    request = urllib.request.Request(
        github_release_api_url(repository),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MaintiQ-Predict-update-checker",
        },
    )
    token = os.environ.get("MAINTIQ_GITHUB_TOKEN", "").strip()
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return UpdateCheckResult(
            status="unavailable",
            current_version=current_version,
            release_url=github_release_page_url(repository),
            message=f"릴리즈 정보를 확인할 수 없습니다. GitHub 응답: HTTP {error.code}",
        )
    except Exception as error:
        return UpdateCheckResult(
            status="unavailable",
            current_version=current_version,
            release_url=github_release_page_url(repository),
            message=f"업데이트 확인에 실패했습니다. 네트워크 또는 저장소 설정을 확인하세요. ({error})",
        )

    latest = str(payload.get("tag_name") or payload.get("name") or "").strip()
    release_url = str(payload.get("html_url") or github_release_page_url(repository))
    if not latest:
        return UpdateCheckResult(
            status="unavailable",
            current_version=current_version,
            release_url=release_url,
            message="최신 릴리즈 버전을 읽을 수 없습니다.",
        )
    if is_newer_version(latest, current_version):
        return UpdateCheckResult(
            status="update_available",
            current_version=current_version,
            latest_version=latest,
            release_url=release_url,
            message=f"새 버전 {latest}이 있습니다.",
        )
    return UpdateCheckResult(
        status="up_to_date",
        current_version=current_version,
        latest_version=latest,
        release_url=release_url,
        message="현재 설치된 버전이 최신입니다.",
    )
