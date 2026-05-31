from __future__ import annotations

from pathlib import Path

from desktop_app.report_history import (
    append_report_history,
    classify_report_error,
    latest_successful_report,
    read_report_history,
    save_report_snapshot,
)


def test_report_history_append_read_and_latest_success(tmp_path: Path) -> None:
    history_path = tmp_path / "ai_report_history.jsonl"
    report_path = tmp_path / "report.md"
    report_path.write_text("# Report\n\n내용", encoding="utf-8")

    append_report_history(
        status="error",
        provider="gemini",
        mode="standard",
        model="gemini-test",
        template="operator",
        length="standard",
        error_type="connection_failed",
        error_message="temporary failure",
        history_path=history_path,
    )
    append_report_history(
        status="success",
        provider="gemini",
        mode="standard",
        model="gemini-test",
        template="operator",
        length="short",
        report_path=report_path,
        report_text=report_path.read_text(encoding="utf-8"),
        history_path=history_path,
    )

    all_records = read_report_history(history_path=history_path)
    success_records = read_report_history(history_path=history_path, status_filter="success")
    latest = latest_successful_report(history_path)

    assert len(all_records) == 2
    assert len(success_records) == 1
    assert latest is not None
    assert latest["status"] == "success"
    assert latest["length"] == "short"
    assert "API" not in latest
    assert "key" not in latest


def test_report_snapshot_and_error_classification(tmp_path: Path, monkeypatch) -> None:
    from desktop_app import report_history

    monkeypatch.setattr(report_history, "REPORT_ARCHIVE_DIR", tmp_path / "archive")
    snapshot = save_report_snapshot("manager report body", created_at="2026-05-13T10:00:00+00:00")

    assert snapshot.exists()
    assert snapshot.read_text(encoding="utf-8") == "manager report body"
    assert classify_report_error("API key format error") == "key_format_error"
    assert classify_report_error("model permission denied") == "model_access_error"
    assert classify_report_error("error_code: insufficient_quota") == "quota_error"
