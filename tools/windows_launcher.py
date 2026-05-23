"""Windows launcher for the local predictive-maintenance dashboard.

This EXE wrapper intentionally does not bundle Python dependencies. It starts
the existing project-local virtual environment and Streamlit apps, then opens
the browser. Passwords are passed only to the child process environment.
"""

from __future__ import annotations

import argparse
import getpass
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


USER_MODE = {
    "label": "사용자 대시보드",
    "port": 8501,
    "app_path": Path("app") / "dashboard.py",
    "password_env": "APP_OPERATOR_PASSWORD",
}

ADMIN_MODE = {
    "label": "Admin 콘솔",
    "port": 8502,
    "app_path": Path("app") / "admin_dashboard.py",
    "password_env": "APP_ADMIN_PASSWORD",
}

MODES = {"user": USER_MODE, "admin": ADMIN_MODE}


def executable_path() -> Path:
    """Return the current script or frozen executable path."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()


def find_project_root() -> Path | None:
    """Find the repository folder that contains .venv and app files."""
    start_points = [
        Path.cwd().resolve(),
        executable_path().parent.resolve(),
        executable_path().parent.parent.resolve(),
    ]
    for start in start_points:
        for candidate in [start, *start.parents]:
            python_exe = candidate / ".venv" / "Scripts" / "python.exe"
            user_app = candidate / USER_MODE["app_path"]
            admin_app = candidate / ADMIN_MODE["app_path"]
            if python_exe.exists() and user_app.exists() and admin_app.exists():
                return candidate
    return None


def is_port_open(port: int) -> bool:
    """Return True when localhost already accepts connections on a port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_http(url: str, timeout_seconds: int) -> bool:
    """Wait until Streamlit responds with any HTTP response."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return 200 <= response.status < 500
        except Exception:
            time.sleep(0.5)
    return False


def choose_mode(default: str = "user") -> str:
    """Ask the operator which app to launch."""
    print()
    print("실행할 앱을 선택하세요.")
    print("  1. 사용자 대시보드")
    print("  2. Admin 콘솔")
    choice = input(f"선택 [1/2, 기본값 {default}]: ").strip()
    if choice == "2":
        return "admin"
    if choice == "1" or choice == "":
        return default
    print("알 수 없는 선택입니다. 사용자 대시보드를 실행합니다.")
    return default


def read_password(env_name: str, supplied: str | None) -> str:
    """Read a password without saving it to disk."""
    if supplied:
        return supplied
    existing = os.environ.get(env_name)
    if existing:
        return existing
    print()
    print("비밀번호는 이 실행 세션에서만 사용됩니다.")
    print("파일, .env, Git 기록에는 저장하지 않습니다.")
    try:
        password = getpass.getpass("대시보드 비밀번호: ")
    except Exception:
        password = input("대시보드 비밀번호: ")
    if not password.strip():
        raise ValueError("비밀번호가 비어 있어 실행을 중단합니다.")
    return password


def build_streamlit_command(root: Path, mode_config: dict) -> list[str]:
    """Build the Streamlit command for one dashboard mode."""
    python_exe = root / ".venv" / "Scripts" / "python.exe"
    app_path = root / mode_config["app_path"]
    return [
        str(python_exe),
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(mode_config["port"]),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]


def launch_dashboard(
    root: Path,
    mode: str,
    password: str,
    open_browser: bool,
    timeout_seconds: int,
    smoke_test: bool,
    port_override: int | None = None,
) -> int:
    """Launch Streamlit and keep the console alive until the user stops it."""
    mode_config = MODES[mode]
    port = int(port_override or mode_config["port"])
    url = f"http://127.0.0.1:{port}"

    if is_port_open(port):
        print()
        print(f"{mode_config['label']} 포트 {port}가 이미 사용 중입니다.")
        print("이미 실행 중인 앱일 수 있으므로 새 서버를 시작하지 않습니다.")
        print(f"브라우저에서 확인: {url}")
        if open_browser:
            webbrowser.open(url)
        return 0

    env = os.environ.copy()
    env[str(mode_config["password_env"])] = password

    print()
    print(f"{mode_config['label']}을 시작합니다.")
    print(f"프로젝트 폴더: {root}")
    print(f"주소: {url}")
    print("종료하려면 이 창에서 Ctrl+C를 누르세요.")

    process = subprocess.Popen(
        build_streamlit_command(root, {**mode_config, "port": port}),
        cwd=str(root),
        env=env,
    )
    try:
        ready = wait_for_http(url, timeout_seconds)
        if ready:
            print("앱이 준비되었습니다.")
            if open_browser:
                webbrowser.open(url)
        else:
            print("제한 시간 안에 앱 응답을 확인하지 못했습니다. 위 로그를 확인하세요.")

        if smoke_test:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            return 0 if ready else 1

        return process.wait()
    except KeyboardInterrupt:
        print()
        print("종료 요청을 받았습니다. 서버를 정리합니다.")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the local Windows dashboard app.")
    parser.add_argument("--mode", choices=["user", "admin"], help="Launch mode. Omit for menu.")
    parser.add_argument("--password", help="Session-only dashboard password. Prefer interactive input.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--port", type=int, help="Override the default Streamlit port. Mostly for smoke tests.")
    parser.add_argument("--timeout-seconds", type=int, default=45, help="Startup HTTP wait timeout.")
    parser.add_argument("--smoke-test", action="store_true", help="Start, wait for HTTP, then stop automatically.")
    parser.add_argument("--check", action="store_true", help="Only check project-root and venv detection.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = find_project_root()
    if root is None:
        print("프로젝트 루트를 찾지 못했습니다.")
        print("이 실행기는 .venv, app, data, outputs가 있는 프로젝트 폴더 안에서 실행해야 합니다.")
        print("먼저 다음 설치를 완료하세요:")
        print("  py -3 -m venv .venv")
        print("  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        return 1

    python_exe = root / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        print(f"가상환경 Python을 찾지 못했습니다: {python_exe}")
        return 1

    if args.check:
        print("실행기 점검 성공")
        print(f"프로젝트 폴더: {root}")
        print(f"Python: {python_exe}")
        return 0

    mode = args.mode or choose_mode()
    mode_config = MODES[mode]
    try:
        password = read_password(str(mode_config["password_env"]), args.password)
    except ValueError as error:
        print(error)
        return 1

    return launch_dashboard(
        root=root,
        mode=mode,
        password=password,
        open_browser=not args.no_browser,
        timeout_seconds=max(5, int(args.timeout_seconds)),
        smoke_test=bool(args.smoke_test),
        port_override=args.port,
    )


if __name__ == "__main__":
    raise SystemExit(main())
