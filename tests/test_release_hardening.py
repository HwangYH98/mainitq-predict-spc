from __future__ import annotations

from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def test_official_entrypoints_and_dev_script_layout() -> None:
    official_entrypoints = [
        "01_Run_MaintiQ_Predict.bat",
        "02_Run_Admin_Console.bat",
        "03_Build_User_Installer.bat",
        "04_Run_Streamlit_Dashboard.bat",
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
        "run_streamlit_dashboard.bat",
    ]
    for relative in legacy_root_scripts:
        assert not (ROOT / relative).exists(), f"Legacy script should not stay in the root: {relative}"

    moved_scripts = [
        "scripts/dev/run_desktop_app.bat",
        "scripts/dev/run_admin_dashboard.bat",
        "scripts/dev/run_streamlit_dashboard.bat",
        "scripts/dev/build_desktop_app.bat",
        "scripts/dev/build_desktop_installer.bat",
        "scripts/dev/lite/build_desktop_lite_app.bat",
        "scripts/dev/lite/build_desktop_lite_installer.bat",
    ]
    for relative in moved_scripts:
        assert (ROOT / relative).exists(), f"Moved development script is missing: {relative}"

    installer_entrypoint = (ROOT / "03_Build_User_Installer.bat").read_text(encoding="utf-8")
    assert "scripts\\dev\\build_desktop_installer.bat" in installer_entrypoint

    streamlit_entrypoint = (ROOT / "04_Run_Streamlit_Dashboard.bat").read_text(encoding="utf-8")
    assert "set /p" not in streamlit_entrypoint
    assert "Set-Clipboard" in streamlit_entrypoint
    assert "Login ID: operator_01" in streamlit_entrypoint
    assert "requirements-lock.txt" in streamlit_entrypoint

    admin_entrypoint = (ROOT / "02_Run_Admin_Console.bat").read_text(encoding="utf-8")
    assert "Start-Process '%ADMIN_CONSOLE_URL%'" in admin_entrypoint
    assert "Login ID: admin" in admin_entrypoint
    assert "requirements-lock.txt" in admin_entrypoint

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "release\\MaintiQ_Predict_Setup.exe" in readme
    assert "operator/Admin validation console" in readme
    assert ".\\04_Run_Streamlit_Dashboard.bat" in readme
    assert ".\\02_Run_Admin_Console.bat" in readme
    assert "Accepted research run" in readme


def test_streamlit_cloud_deployment_entrypoints_are_separated() -> None:
    operator_entrypoint = ROOT / "app" / "operator_dashboard.py"
    admin_entrypoint = ROOT / "app" / "admin_dashboard.py"
    app_requirements = ROOT / "app" / "requirements.txt"

    assert operator_entrypoint.exists()
    assert admin_entrypoint.exists()
    assert app_requirements.exists()

    operator_source = operator_entrypoint.read_text(encoding="utf-8")
    admin_source = admin_entrypoint.read_text(encoding="utf-8")
    requirements = app_requirements.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert 'dashboard.main(app_mode="user")' in operator_source
    assert 'dashboard.main(app_mode="admin")' in admin_source
    assert "app/operator_dashboard.py" in readme
    assert "app/admin_dashboard.py" in readme
    assert "[auth]" in readme
    assert "Python `3.12`" in readme

    for required in ["streamlit", "pandas", "numpy", "scikit-learn", "xgboost", "matplotlib", "joblib"]:
        assert required in requirements

    for desktop_only in ["PySide6", "pytest", "python-docx", "python-pptx", "pyinstaller"]:
        assert desktop_only not in requirements


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
