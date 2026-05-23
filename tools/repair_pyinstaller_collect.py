from __future__ import annotations

import ast
from pathlib import Path
import shutil


APP_NAME = "MaintiQ_Predict"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    app_dir = root / "dist" / APP_NAME
    toc_path = root / "build" / APP_NAME / "COLLECT-00.toc"
    if not toc_path.exists():
        raise SystemExit(f"Missing PyInstaller collect manifest: {toc_path}")
    if not app_dir.exists():
        raise SystemExit(f"Missing PyInstaller dist folder: {app_dir}")

    entries = ast.literal_eval(toc_path.read_text(encoding="utf-8"))[0]
    copied = 0
    skipped = 0
    for dest_name, source_name, kind in entries:
        source = Path(source_name)
        if not source.exists() or not source.is_file():
            skipped += 1
            continue
        if kind == "EXECUTABLE":
            target = app_dir / dest_name
        else:
            target = app_dir / "_internal" / dest_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
            copied += 1

    python_dll = app_dir / "_internal" / "python314.dll"
    if not python_dll.exists():
        raise SystemExit(f"Missing required Python runtime DLL after repair: {python_dll}")

    print("PyInstaller runtime files verified.")
    print(f"copied: {copied}")
    print(f"skipped missing: {skipped}")


if __name__ == "__main__":
    main()
