from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop_app.pages import (
    MainWindow,
    default_actor,
    run_check,
    run_click_workflow_test,
    run_engine_smoke_test,
    run_workflow_smoke_test,
    stylesheet,
)
from desktop_app.runtime import PROJECT_ROOT, export_crash_logs, write_error_log


def run_app(smoke_test: bool = False) -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(stylesheet())
    window = MainWindow(default_actor())
    window.show()
    if smoke_test:
        QTimer.singleShot(1000, app.quit)
    return app.exec()


def save_screenshot(output_path: str) -> int:
    """Render the app and save a screenshot without showing secrets."""
    app = QApplication(sys.argv)
    app.setStyleSheet(stylesheet())
    window = MainWindow(default_actor())
    window.show()
    app.processEvents()
    pixmap = window.grab()
    path = Path(output_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path)):
        raise RuntimeError(f"Could not save screenshot: {path}")
    print(f"Desktop app screenshot saved: {path}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MaintiQ Predict native desktop app.")
    parser.add_argument("--check", action="store_true", help="Check project files without opening the UI.")
    parser.add_argument("--smoke-test", action="store_true", help="Open the UI briefly and exit. Useful for build tests.")
    parser.add_argument("--engine-smoke-test", action="store_true", help="Run prediction-engine checks without opening the UI.")
    parser.add_argument("--workflow-smoke-test", action="store_true", help="Run the main GUI workflow without user input.")
    parser.add_argument("--click-workflow-test", action="store_true", help="Run the main GUI workflow through button clicks.")
    parser.add_argument("--screenshot", help="Save a product screenshot.")
    parser.add_argument("--export-crash-logs", nargs="?", const="", help="Export crash logs to a ZIP file.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv or sys.argv[1:])
        if args.check:
            return run_check()
        if args.engine_smoke_test:
            return run_engine_smoke_test()
        if args.workflow_smoke_test:
            return run_workflow_smoke_test()
        if args.click_workflow_test:
            return run_click_workflow_test()
        if args.screenshot:
            return save_screenshot(args.screenshot)
        if args.export_crash_logs is not None:
            output = Path(args.export_crash_logs) if args.export_crash_logs else None
            zip_path = export_crash_logs(output)
            print(f"Crash logs exported: {zip_path}")
            return 0
        return run_app(smoke_test=args.smoke_test)
    except Exception:
        write_error_log()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
