from __future__ import annotations

from pathlib import Path
import sys


REQUIRED_FILES = [
    "MaintiQ_Predict.exe",
    "_internal/python314.dll",
    "_internal/VCRUNTIME140.dll",
    "_internal/PySide6/Qt6Core.dll",
    "_internal/xgboost/lib/xgboost.dll",
    "data/ai4i2020.csv",
    "samples/company_sensor_sample.csv",
    "src/data.py",
    "src/operations_store.py",
    "src/preprocessing_prediction_engine.py",
    "src/realtime_ops.py",
    "src/scania_product_engine.py",
    "outputs/ai_report_context.json",
    "outputs/metrics.json",
    "outputs/scania_cost_optimized_model.joblib",
    "outputs/spc_timeseries.csv",
    "outputs/threshold_summary.json",
]

FORBIDDEN_NAMES = {
    ".env",
    "operations.db",
}

FORBIDDEN_DIR_NAMES = {
    "data_external",
    "local_presentation_notes",
    ".git",
    ".venv",
}

FORBIDDEN_SUFFIXES = {
    ".key",
}

OPTIONAL_BLOAT_PATHS = [
    "_internal/xgboost/testing",
    "_internal/xgboost/dask",
    "_internal/xgboost/spark",
]


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        print("Usage: python tools/validate_desktop_distribution.py dist/MaintiQ_Predict")
        return 2

    app_dir = Path(args[0]).resolve()
    if not app_dir.exists():
        print(f"Distribution folder does not exist: {app_dir}")
        return 1

    missing = [relative for relative in REQUIRED_FILES if not (app_dir / relative).exists()]

    forbidden: list[str] = []
    for path in app_dir.rglob("*"):
        relative = str(path.relative_to(app_dir))
        if path.is_dir() and path.name in FORBIDDEN_DIR_NAMES:
            forbidden.append(relative)
        if path.is_file():
            lower_name = path.name.lower()
            if lower_name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
                forbidden.append(relative)

    if missing:
        print("MaintiQ Predict distribution validation failed: missing required files.")
        for item in missing:
            print(f"- {item}")
    if forbidden:
        print("MaintiQ Predict distribution validation failed: forbidden files/folders included.")
        for item in forbidden:
            print(f"- {item}")
    if missing or forbidden:
        return 1

    file_count = sum(1 for path in app_dir.rglob("*") if path.is_file())
    warning_paths = [relative for relative in OPTIONAL_BLOAT_PATHS if (app_dir / relative).exists()]
    pycache_count = sum(1 for path in app_dir.rglob("__pycache__") if path.is_dir())
    print("MaintiQ Predict distribution validation passed.")
    print(f"folder: {app_dir}")
    print(f"files: {file_count}")
    if warning_paths or pycache_count:
        print("warnings:")
        for item in warning_paths:
            print(f"- optional package folder still included: {item}")
        if pycache_count:
            print(f"- __pycache__ folders still included: {pycache_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
