from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED_PREFIXES = (
    ".venv/",
    ".codex/",
    "build/",
    "dist/",
    "release/",
    "data_external/",
    "local_presentation_notes/",
    "__pycache__/",
    "app/__pycache__/",
    "desktop_app/__pycache__/",
    "src/__pycache__/",
    "tools/__pycache__/",
    "outputs/realtime_stream/",
    "outputs/work_order_drafts/",
)

ALLOWED_OUTPUT_FILES = {
    "outputs/thesis_evidence_pack.md",
    "outputs/industrial_engineering_evidence.md",
    "outputs/field_validation_protocol.md",
    "outputs/field_data_template.csv",
    "outputs/field_cost_template.csv",
    "outputs/run_to_failure_evidence_summary.md",
}

FORBIDDEN_TRACKED_FILES = {
    ".env",
    "outputs/operations.db",
    "outputs/operations_lite.db",
}

FORBIDDEN_SUFFIXES = (
    ".key",
    ".spec",
)

SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-[0-9A-Za-z_-]{20,}"),
]

SKIP_SCAN_DIRS = {
    ".git",
    ".venv",
    ".codex",
    "build",
    "dist",
    "release",
    "data_external",
    "local_presentation_notes",
    "__pycache__",
}

SKIP_SCAN_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".db",
    ".joblib",
    ".exe",
    ".dll",
    ".pyd",
    ".zip",
}


def git_status_entries() -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append((status, path))
    return entries


def git_tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def find_forbidden_status_paths(paths: list[str]) -> list[str]:
    problems: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        lower = normalized.lower()
        if normalized.startswith("outputs/") and normalized not in ALLOWED_OUTPUT_FILES:
            problems.append(normalized)
            continue
        if normalized in FORBIDDEN_TRACKED_FILES:
            problems.append(normalized)
            continue
        if any(lower.startswith(prefix.lower()) for prefix in FORBIDDEN_TRACKED_PREFIXES):
            problems.append(normalized)
            continue
        if any(lower.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            problems.append(normalized)
    return sorted(set(problems))


def find_forbidden_status_entries(entries: list[tuple[str, str]]) -> list[str]:
    active_paths: list[str] = []
    for status, path in entries:
        # Staged removals are allowed: this is how legacy generated artifacts
        # are removed from future commits while keeping local copies intact.
        if status[0] == "D":
            continue
        active_paths.append(path)
    return find_forbidden_status_paths(active_paths)


def find_secret_patterns() -> list[str]:
    matches: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(ROOT)
        if set(relative.parts) & SKIP_SCAN_DIRS:
            continue
        if path.suffix.lower() in SKIP_SCAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            matches.append(str(relative))
    return sorted(matches)


def main() -> int:
    status_entries = git_status_entries()
    tracked_paths = git_tracked_paths()
    forbidden = sorted(
        set(find_forbidden_status_entries(status_entries) + find_forbidden_status_paths(tracked_paths))
    )
    secrets = find_secret_patterns()

    if forbidden:
        print("GitHub upload scope check failed: forbidden paths are present in git status.")
        for item in forbidden:
            print(f"- {item}")
    if secrets:
        print("GitHub upload scope check failed: API key-like patterns found.")
        for item in secrets:
            print(f"- {item}")
    if forbidden or secrets:
        return 1

    print("GitHub upload scope check passed.")
    print(f"git_status_paths_checked={len(status_entries)}")
    print(f"git_tracked_paths_checked={len(tracked_paths)}")
    print("api_key_pattern_matches=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
