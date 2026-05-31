from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from desktop_app.runtime import OUTPUT_DIR, now_iso


REPORT_HISTORY_PATH = OUTPUT_DIR / "ai_report_history.jsonl"
REPORT_ARCHIVE_DIR = OUTPUT_DIR / "ai_reports"


def _safe_timestamp(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_")
    return cleaned or "report"


def report_preview(report_text: str, limit: int = 320) -> str:
    text = " ".join(str(report_text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def save_report_snapshot(report_text: str, created_at: str | None = None) -> Path:
    REPORT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = _safe_timestamp(created_at or now_iso())
    path = REPORT_ARCHIVE_DIR / f"ai_report_{timestamp}.md"
    path.write_text(report_text, encoding="utf-8")
    return path


def append_report_history(
    *,
    status: str,
    provider: str = "",
    mode: str = "",
    model: str = "",
    template: str = "",
    length: str = "",
    report_path: str | Path = "",
    error_message: str = "",
    error_type: str = "",
    report_text: str = "",
    history_path: Path = REPORT_HISTORY_PATH,
) -> dict[str, Any]:
    """Append one AI report history record without storing API keys."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = now_iso()
    record = {
        "created_at": created_at,
        "status": status,
        "provider": provider,
        "mode": mode,
        "model": model,
        "template": template,
        "length": length,
        "report_path": str(report_path) if report_path else "",
        "error_type": error_type,
        "error_message": str(error_message or ""),
        "report_preview": report_preview(report_text),
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_report_history(
    *,
    history_path: Path = REPORT_HISTORY_PATH,
    status_filter: str = "all",
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if status_filter != "all" and record.get("status") != status_filter:
            continue
        records.append(record)
    records.reverse()
    return records[:limit]


def latest_successful_report(history_path: Path = REPORT_HISTORY_PATH) -> dict[str, Any] | None:
    for record in read_report_history(history_path=history_path, status_filter="success", limit=1):
        return record
    return None


def classify_report_error(error: Exception | str) -> str:
    message = str(error).lower()
    if "insufficient_quota" in message or "quota" in message or "billing" in message:
        return "quota_error"
    if "api key" in message and ("format" in message or "invalid" in message or "unsupported" in message):
        return "key_format_error"
    if "empty" in message or "빈 응답" in message:
        return "empty_response"
    if "model" in message or "permission" in message or "access" in message or "권한" in message:
        return "model_access_error"
    if "http" in message or "connection" in message or "timeout" in message or "연결" in message:
        return "connection_failed"
    if "save" in message or "write" in message or "저장" in message:
        return "report_save_failed"
    return "report_generation_failed"
