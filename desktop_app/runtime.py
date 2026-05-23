from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
import urllib.error
import urllib.request
import uuid
import zipfile

_DLL_DIRECTORY_HANDLES = []


def unique_existing_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    existing: list[Path] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        existing.append(resolved)
    return existing


def find_project_root() -> Path:
    """Find the project folder when running from source or a PyInstaller build."""
    candidates: list[Path] = []
    env_root = os.environ.get("MAINTIQ_PROJECT_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend(
        [
            Path.cwd(),
            Path(__file__).resolve().parent,
            Path(__file__).resolve().parents[1],
        ]
    )
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([exe_dir, *exe_dir.parents])

    for candidate in candidates:
        for path in [candidate, *candidate.parents]:
            if (path / "data" / "ai4i2020.csv").exists() and (path / "outputs").exists():
                return path
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = find_project_root()
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"


def frozen_internal_candidates() -> list[Path]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir / "_internal",
                Path(getattr(sys, "_MEIPASS", "")),
            ]
        )
    candidates.extend(
        [
            PROJECT_ROOT / "_internal",
            PROJECT_ROOT,
        ]
    )
    return unique_existing_paths(candidates)


def configure_frozen_runtime_paths() -> None:
    """Expose bundled runtime folders before ML libraries are imported."""
    for internal_dir in frozen_internal_candidates():
        if (internal_dir / "xgboost" / "__init__.py").exists() and str(internal_dir) not in sys.path:
            sys.path.insert(0, str(internal_dir))

        xgboost_lib_dir = internal_dir / "xgboost" / "lib"
        if (xgboost_lib_dir / "xgboost.dll").exists():
            if hasattr(os, "add_dll_directory"):
                _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(xgboost_lib_dir)))
            current_path = os.environ.get("PATH", "")
            xgboost_path = str(xgboost_lib_dir)
            if xgboost_path.lower() not in current_path.lower():
                os.environ["PATH"] = xgboost_path + os.pathsep + current_path


configure_frozen_runtime_paths()

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))



def read_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def crash_log_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", os.environ.get("TEMP", str(PROJECT_ROOT))))
    return base / "MaintiQ Predict" / "logs"


def write_error_log() -> None:
    """Write frozen-app diagnostics to a user-visible temp file."""
    try:
        log_dir = crash_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_path = log_dir / f"crash_{timestamp}.log"
        lines = [
            "MaintiQ Predict error diagnostics",
            f"created_at={datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
            f"PROJECT_ROOT={PROJECT_ROOT}",
            f"sys.executable={sys.executable}",
            f"sys.frozen={getattr(sys, 'frozen', False)}",
            f"sys._MEIPASS={getattr(sys, '_MEIPASS', '')}",
            "xgboost candidate paths:",
        ]
        for internal_dir in frozen_internal_candidates():
            dll_path = internal_dir / "xgboost" / "lib" / "xgboost.dll"
            lines.append(f"- {dll_path} exists={dll_path.exists()}")
        lines.extend(["", traceback.format_exc()])
        log_path.write_text("\n".join(lines), encoding="utf-8")
        legacy_path = Path(os.environ.get("TEMP", str(PROJECT_ROOT))) / "MaintiQ_Predict_error.log"
        legacy_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass


def export_crash_logs(destination: Path | None = None) -> Path:
    """Export local crash logs as a ZIP for support/debugging."""
    log_dir = crash_log_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if destination is None:
        destination = OUTPUT_DIR / f"maintiq_crash_logs_{timestamp}.zip"
    if not destination.is_absolute():
        destination = PROJECT_ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if log_dir.exists():
            for path in sorted(log_dir.glob("*.log")):
                archive.write(path, arcname=path.name)
        readme = (
            "MaintiQ Predict crash log export\n"
            f"created_at={datetime.now(timezone.utc).replace(microsecond=0).isoformat()}\n"
            "API keys and passwords are not intentionally stored in these logs.\n"
        )
        archive.writestr("README.txt", readme)
    return destination
