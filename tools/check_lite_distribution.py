from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"

REQUIRED_RELATIVE_PATHS = [
    "MaintiQ_Predict_Lite.exe",
    "_internal/python314.dll",
    "_internal/PySide6/Qt6Core.dll",
    "samples/company_sensor_sample.csv",
    "_internal/samples/company_sensor_sample.csv",
    "_internal/sample_company_sensor.csv",
]

FORBIDDEN_NAME_PARTS = [
    "xgboost",
    "shap",
    "numba",
    "llvmlite",
    "pyarrow",
    "matplotlib",
]

FORBIDDEN_PATH_PARTS = [
    ".env",
    "operations.db",
    "operations_lite.db",
    "data_external",
    "local_presentation_notes",
]


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def format_mb(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def find_forbidden(app_dir: Path) -> list[str]:
    problems: list[str] = []
    for path in app_dir.rglob("*"):
        relative = path.relative_to(app_dir).as_posix()
        lower = relative.lower()
        if any(part in lower for part in FORBIDDEN_NAME_PARTS):
            problems.append(relative)
            continue
        if any(part.lower() in lower for part in FORBIDDEN_PATH_PARTS):
            problems.append(relative)
    return sorted(problems)


def write_size_report(lite_dir: Path) -> None:
    full_dir = ROOT / "dist" / "MaintiQ_Predict"
    full_setup = ROOT / "release" / "MaintiQ_Predict_Setup.exe"
    lite_setup = ROOT / "release" / "MaintiQ_Predict_Lite_Setup.exe"
    full_dir_size = folder_size(full_dir)
    lite_dir_size = folder_size(lite_dir)
    full_setup_size = full_setup.stat().st_size if full_setup.exists() else 0
    lite_setup_size = lite_setup.stat().st_size if lite_setup.exists() else 0

    def reduction(full_size: int, lite_size: int) -> str:
        if full_size <= 0:
            return "N/A"
        return f"{(1 - lite_size / full_size) * 100:.1f}%"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = OUTPUT_DIR / "desktop_lite_distribution_size_report.md"
    report.write_text(
        "\n".join(
            [
                "# MaintiQ Predict Lite Distribution Size Report",
                "",
                "| Artifact | Full | Lite | Reduction |",
                "|---|---:|---:|---:|",
                f"| Portable folder | {format_mb(full_dir_size) if full_dir_size else 'N/A'} | {format_mb(lite_dir_size)} | {reduction(full_dir_size, lite_dir_size)} |",
                f"| Installer EXE | {format_mb(full_setup_size) if full_setup_size else 'N/A'} | {format_mb(lite_setup_size) if lite_setup_size else 'N/A'} | {reduction(full_setup_size, lite_setup_size)} |",
                "",
                "Lite excludes the research runtime packages used by the Full build: xgboost, shap, numba/llvmlite, pyarrow, and matplotlib.",
                "Lite uses deterministic lightweight risk scoring and is not intended to reproduce the Full research model metrics.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MaintiQ Predict Lite distribution boundaries.")
    parser.add_argument("app_dir", type=Path)
    args = parser.parse_args()
    app_dir = args.app_dir

    missing = [path for path in REQUIRED_RELATIVE_PATHS if not (app_dir / path).exists()]
    forbidden = find_forbidden(app_dir) if app_dir.exists() else []

    if missing:
        print("Lite distribution check failed: required files are missing.")
        for item in missing:
            print(f"- {item}")
    if forbidden:
        print("Lite distribution check failed: forbidden research runtime files were included.")
        for item in forbidden[:80]:
            print(f"- {item}")
        if len(forbidden) > 80:
            print(f"... {len(forbidden) - 80} more")
    if missing or forbidden:
        return 1

    write_size_report(app_dir)
    print("Lite distribution check passed.")
    print(f"portable_size={format_mb(folder_size(app_dir))}")
    print("forbidden_runtime_matches=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
