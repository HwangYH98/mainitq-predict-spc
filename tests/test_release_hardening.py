from __future__ import annotations

from pathlib import Path
import zipfile


def test_crash_log_export_creates_zip(tmp_path: Path, monkeypatch) -> None:
    from desktop_app import runtime

    local_app_data = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    log_dir = runtime.crash_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "crash_sample.log").write_text("sample crash", encoding="utf-8")

    zip_path = runtime.export_crash_logs(tmp_path / "crash_logs.zip")

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as archive:
        assert "crash_sample.log" in archive.namelist()
        assert "README.txt" in archive.namelist()

