from __future__ import annotations

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def test_official_entrypoints_and_dev_script_layout() -> None:
    official_entrypoints = [
        "01_Run_MaintiQ_Predict.bat",
        "02_Run_Admin_Console.bat",
        "03_Build_User_Installer.bat",
    ]
    for relative in official_entrypoints:
        assert (ROOT / relative).exists(), f"Missing official root entrypoint: {relative}"

    legacy_root_scripts = [
        "run_desktop_app.bat",
        "run_admin_dashboard.bat",
        "build_desktop_app.bat",
        "build_desktop_installer.bat",
        "build_desktop_lite_app.bat",
        "build_desktop_lite_installer.bat",
    ]
    for relative in legacy_root_scripts:
        assert not (ROOT / relative).exists(), f"Legacy script should not stay in the root: {relative}"

    moved_scripts = [
        "scripts/dev/run_desktop_app.bat",
        "scripts/dev/run_admin_dashboard.bat",
        "scripts/dev/build_desktop_app.bat",
        "scripts/dev/build_desktop_installer.bat",
        "scripts/dev/lite/build_desktop_lite_app.bat",
        "scripts/dev/lite/build_desktop_lite_installer.bat",
    ]
    for relative in moved_scripts:
        assert (ROOT / relative).exists(), f"Moved development script is missing: {relative}"

    installer_entrypoint = (ROOT / "03_Build_User_Installer.bat").read_text(encoding="utf-8")
    assert "scripts\\dev\\build_desktop_installer.bat" in installer_entrypoint

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "release\\MaintiQ_Predict_Setup.exe" in readme
    assert "Streamlit은 GitHub에 소스가 올라가는 로컬 운영/Admin 검증 화면" in readme


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
