from __future__ import annotations

import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_DIR = PROJECT_ROOT / "dist" / "MaintiQ_Predict"
SIZE_REPORT = PROJECT_ROOT / "outputs" / "desktop_distribution_size_report.md"

PRUNE_RELATIVE_DIRS = [
    "_internal/xgboost/testing",
    "_internal/xgboost/dask",
    "_internal/xgboost/spark",
]


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def remove_dir(path: Path, app_dir: Path) -> tuple[str, int] | None:
    resolved = path.resolve()
    app_resolved = app_dir.resolve()
    if not str(resolved).startswith(str(app_resolved)):
        raise ValueError(f"Refusing to remove outside distribution folder: {path}")
    if not path.exists():
        return None
    size = folder_size(path)
    shutil.rmtree(path)
    return str(path.relative_to(app_dir)), size


def prune_distribution(app_dir: Path = DEFAULT_APP_DIR) -> dict[str, object]:
    if not app_dir.exists():
        raise FileNotFoundError(f"distribution folder was not found: {app_dir}")

    before_size = folder_size(app_dir)
    removed: list[tuple[str, int]] = []
    for relative in PRUNE_RELATIVE_DIRS:
        result = remove_dir(app_dir / relative, app_dir)
        if result:
            removed.append(result)

    for cache_dir in list(app_dir.rglob("__pycache__")):
        result = remove_dir(cache_dir, app_dir)
        if result:
            removed.append(result)

    after_size = folder_size(app_dir)
    report = {
        "app_dir": str(app_dir),
        "before_size_bytes": before_size,
        "after_size_bytes": after_size,
        "removed_size_bytes": before_size - after_size,
        "removed_paths": removed,
    }
    write_report(report)
    return report


def write_report(report: dict[str, object]) -> None:
    SIZE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    removed_paths = report["removed_paths"]
    rows = [
        "# Desktop Distribution Size Report",
        "",
        f"- Before prune: {int(report['before_size_bytes']) / (1024 * 1024):.2f} MB",
        f"- After prune: {int(report['after_size_bytes']) / (1024 * 1024):.2f} MB",
        f"- Removed: {int(report['removed_size_bytes']) / (1024 * 1024):.2f} MB",
        "",
        "## Removed Paths",
        "",
    ]
    if removed_paths:
        for path, size in removed_paths:  # type: ignore[assignment]
            rows.append(f"- `{path}`: {size / (1024 * 1024):.2f} MB")
    else:
        rows.append("- No optional paths were found.")
    SIZE_REPORT.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    app_dir = Path(args[0]).resolve() if args else DEFAULT_APP_DIR
    report = prune_distribution(app_dir)
    print("Desktop distribution prune completed.")
    print(f"before_mb: {int(report['before_size_bytes']) / (1024 * 1024):.2f}")
    print(f"after_mb: {int(report['after_size_bytes']) / (1024 * 1024):.2f}")
    print(f"removed_mb: {int(report['removed_size_bytes']) / (1024 * 1024):.2f}")
    print(f"report: {SIZE_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
