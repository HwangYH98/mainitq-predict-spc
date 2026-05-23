from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_app_version() -> str:
    text = read_text(ROOT / "desktop_app" / "version.py")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        raise AssertionError("APP_VERSION was not found in desktop_app/version.py")
    return match.group(1)


def extract_inno_version(path: Path) -> str:
    text = read_text(path)
    match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', text)
    if not match:
        raise AssertionError(f"MyAppVersion was not found in {path}")
    return match.group(1)


def git_status_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        paths.append(line[3:].replace("\\", "/"))
    return paths


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check MaintiQ Predict release readiness.")
    parser.add_argument(
        "--require-signed",
        action="store_true",
        help="Fail unless existing Full/Lite installers have a Valid Authenticode signature.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    app_version = extract_app_version()
    installer_versions = {
        "full": extract_inno_version(ROOT / "installer" / "MaintiQ_Predict.iss"),
        "lite": extract_inno_version(ROOT / "installer" / "MaintiQ_Predict_Lite.iss"),
    }
    mismatched = {name: version for name, version in installer_versions.items() if version != app_version}
    if mismatched:
        raise AssertionError(f"Installer version mismatch: app={app_version}, installers={mismatched}")

    changelog = read_text(ROOT / "CHANGELOG.md")
    if f"## {app_version} " not in changelog:
        raise AssertionError(f"CHANGELOG.md has no entry for {app_version}")

    required_docs = [
        ROOT / "docs" / "DISTRIBUTION_POLICY.md",
        ROOT / "docs" / "RELEASE_CHECKLIST.md",
        ROOT / "docs" / "CODE_SIGNING_GUIDE.md",
        ROOT / "docs" / "FIELD_VALIDATION_GUIDE.md",
    ]
    missing_docs = [str(path) for path in required_docs if not path.exists()]
    if missing_docs:
        raise AssertionError("Missing release docs: " + ", ".join(missing_docs))

    forbidden_status = [
        path
        for path in git_status_paths()
        if path.startswith("release/") or path.startswith("dist/") or path.startswith("build/") or path.endswith(".spec")
    ]
    if forbidden_status:
        raise AssertionError("Release/build artifacts are present in git status: " + ", ".join(forbidden_status))

    if args.require_signed:
        from check_windows_signing_status import DEFAULT_TARGETS, powershell_signature_status

        signing_statuses = [powershell_signature_status(path) for path in DEFAULT_TARGETS]
        unsigned = [
            f"{Path(item['path']).name}:{item.get('status')}"
            for item in signing_statuses
            if item.get("exists") == "true" and item.get("status") != "Valid"
        ]
        if unsigned:
            raise AssertionError("Installers are not Authenticode-signed: " + ", ".join(unsigned))

    print("Release readiness check passed.")
    print(f"app_version={app_version}")
    print("installer_versions=matched")
    print("release_artifacts_not_in_git_status=true")
    print(f"signing_required={str(args.require_signed).lower()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Release readiness check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
