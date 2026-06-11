from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANONICAL_COLUMNS = [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]

ALIASES = {
    "Type": ["type", "product_type", "product grade", "product_grade", "grade"],
    "Air temperature [K]": ["air temperature [k]", "air_temp_k", "air_temp_c", "air temperature", "airtemp", "air_temp"],
    "Process temperature [K]": [
        "process temperature [k]",
        "process_temp_k",
        "process_temp_c",
        "process temperature",
        "process_temp",
    ],
    "Rotational speed [rpm]": ["rotational speed [rpm]", "rpm", "speed", "rotational_speed", "rotational speed"],
    "Torque [Nm]": ["torque [nm]", "torque", "motor_torque_nm", "torque_nm"],
    "Tool wear [min]": ["tool wear [min]", "tool_wear", "wear_minutes", "tool_wear_min", "wear"],
}

THRESHOLD = 0.86
POLICY_THRESHOLDS = {
    "precision_first": THRESHOLD,
    "balanced": THRESHOLD,
    "recall_first": THRESHOLD,
}


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = app_root()
SAMPLE_DIR = PROJECT_ROOT / "samples"


def user_data_root() -> Path:
    """Return a writable per-user folder for app outputs."""
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", os.environ.get("TEMP", str(PROJECT_ROOT))))
        return base / "MaintiQ Predict"
    return PROJECT_ROOT


OUTPUT_DIR = user_data_root() / "outputs"
LITE_DB = OUTPUT_DIR / "operations_lite.db"

DEFAULT_SAMPLE_ROWS = [
    {
        "product_grade": "L",
        "air_temp_c": "25.0",
        "process_temp_c": "35.4",
        "rpm": "1551",
        "motor_torque_nm": "42.8",
        "wear_minutes": "0",
    },
    {
        "product_grade": "M",
        "air_temp_c": "31.0",
        "process_temp_c": "45.2",
        "rpm": "1320",
        "motor_torque_nm": "58.4",
        "wear_minutes": "180",
    },
    {
        "product_grade": "H",
        "air_temp_c": "34.5",
        "process_temp_c": "49.7",
        "rpm": "1215",
        "motor_torque_nm": "64.2",
        "wear_minutes": "232",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def runtime_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            internal = Path(meipass).resolve()
            roots.extend([internal, internal.parent])
    roots.append(PROJECT_ROOT)

    unique_roots: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            unique_roots.append(root)
            seen.add(key)
    return unique_roots


def normalize_name(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def infer_mapping(headers: list[str]) -> dict[str, str]:
    normalized = {normalize_name(header): header for header in headers}
    mapping: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        candidates = [canonical, *aliases]
        selected = ""
        for candidate in candidates:
            key = normalize_name(candidate)
            if key in normalized:
                selected = normalized[key]
                break
        mapping[canonical] = selected
    return mapping


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if not headers:
        raise ValueError("CSV에 헤더 행이 없습니다.")
    if not rows:
        raise ValueError("CSV에 데이터 행이 없습니다.")
    return rows, headers


def parse_number(value: Any, default: float = 0.0) -> tuple[float, bool]:
    if value is None:
        return default, False
    text = str(value).strip().replace(",", "")
    if not text:
        return default, False
    try:
        return float(text), True
    except ValueError:
        return default, False


def normalize_type(value: Any) -> tuple[str, bool]:
    text = str(value or "M").strip().upper()
    if text in {"L", "M", "H"}:
        return text, True
    return "M", False


def normalize_row(row: dict[str, str], mapping: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    normalized: dict[str, Any] = {}
    product_type, valid_type = normalize_type(row.get(mapping.get("Type", ""), "M"))
    normalized["Type"] = product_type
    if not valid_type:
        warnings.append("제품 등급 값이 올바르지 않아 M으로 대체됨")

    for canonical in CANONICAL_COLUMNS[1:]:
        source = mapping.get(canonical, "")
        value, ok = parse_number(row.get(source, ""))
        if not source:
            warnings.append(f"매핑 컬럼 누락: {canonical}")
        elif not ok:
            warnings.append(f"숫자 형식 오류: {canonical}")
        if canonical in {"Air temperature [K]", "Process temperature [K]"} and value < 200:
            value += 273.15
        normalized[canonical] = round(value, 4)
    return normalized, warnings


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def risk_components(row: dict[str, Any]) -> dict[str, float]:
    air = float(row["Air temperature [K]"])
    process = float(row["Process temperature [K]"])
    rpm = float(row["Rotational speed [rpm]"])
    torque = float(row["Torque [Nm]"])
    wear = float(row["Tool wear [min]"])
    temp_delta = process - air
    return {
        "thermal_load": clamp((process - 305.0) / 25.0),
        "temperature_gap": clamp((temp_delta - 8.0) / 10.0),
        "speed_deviation": clamp(abs(rpm - 1500.0) / 650.0),
        "torque_load": clamp((torque - 38.0) / 32.0),
        "tool_wear": clamp(wear / 260.0),
    }


def recommendation(probability: float, reasons: list[tuple[str, float]]) -> str:
    top_reason = reasons[0][0].replace("_", " ") if reasons else "센서 패턴"
    if probability >= THRESHOLD:
        return f"설비 상태를 우선 확인하세요. 주요 신호: {top_reason}."
    if probability >= 0.45:
        return f"추세를 관찰하고 센서 단위를 확인하세요. 주요 신호: {top_reason}."
    return "즉시 조치는 필요하지 않습니다. 정기 모니터링을 유지하세요."


def score_row(row: dict[str, Any], quality_penalty: float = 0.0, threshold: float = THRESHOLD) -> dict[str, Any]:
    components = risk_components(row)
    weighted = (
        0.22 * components["thermal_load"]
        + 0.12 * components["temperature_gap"]
        + 0.16 * components["speed_deviation"]
        + 0.25 * components["torque_load"]
        + 0.25 * components["tool_wear"]
    )
    type_adjustment = {"L": 0.03, "M": 0.0, "H": -0.02}.get(str(row["Type"]), 0.0)
    probability = clamp(0.08 + weighted + type_adjustment + quality_penalty)
    priority_score = round(100.0 * probability + 10.0 * quality_penalty, 2)
    reasons = sorted(components.items(), key=lambda item: item[1], reverse=True)[:3]
    return {
        "failure_probability": round(probability, 6),
        "risk_status": "High Risk" if probability >= threshold else "Normal",
        "risk_priority_score": priority_score,
        "key_signals": ", ".join(name.replace("_", " ") for name, _ in reasons),
        "recommendation": recommendation(probability, reasons),
    }


def predict_csv(path: Path, policy_id: str = "balanced") -> dict[str, Any]:
    raw_rows, headers = read_csv_rows(path)
    mapping = infer_mapping(headers)
    policy_id = policy_id if policy_id in POLICY_THRESHOLDS else "balanced"
    threshold = POLICY_THRESHOLDS[policy_id]
    result_rows: list[dict[str, Any]] = []
    warning_count = 0
    for index, raw in enumerate(raw_rows):
        normalized, warnings = normalize_row(raw, mapping)
        warning_count += len(warnings)
        quality_penalty = min(0.15, 0.03 * len(warnings))
        scored = score_row(normalized, quality_penalty=quality_penalty, threshold=threshold)
        result_rows.append(
            {
                "input_row": index,
                "engine_profile": "lite",
                "score_method": "경량 운영 점수",
                "interpretation_note": "빠른 점검 모드 결과는 가벼운 운영 점수이며 정밀 분석 모드 결과와 다를 수 있습니다.",
                "operating_policy": policy_id,
                "selected_threshold": threshold,
                **normalized,
                **scored,
                "quality_warnings": "; ".join(warnings),
            }
        )

    high_risk = sum(1 for row in result_rows if row["risk_status"] == "High Risk")
    max_probability = max(float(row["failure_probability"]) for row in result_rows)
    priority_rows = sorted(result_rows, key=lambda row: (row["risk_priority_score"], row["failure_probability"]), reverse=True)
    for rank, row in enumerate(priority_rows, start=1):
        row["priority_rank"] = rank

    return {
        "runtime_profile": "lite",
        "engine_profile": "lite",
        "score_method": "경량 운영 점수",
        "interpretation_note": "빠른 점검 모드 결과는 가벼운 운영 점수이며 정밀 분석 모드 결과와 다를 수 있습니다.",
        "source_path": str(path),
        "mapping": mapping,
        "rows": result_rows,
        "priority_rows": priority_rows,
        "summary": {
            "row_count": len(result_rows),
            "high_risk_count": high_risk,
            "max_probability": round(max_probability, 6),
            "threshold": threshold,
            "policy_id": policy_id,
            "warning_count": warning_count,
            "engine_note": "빠른 점검 모드는 경량 운영 점수입니다. 정밀 분석 결과는 Full/Admin 환경에서 확인합니다.",
        },
    }


def save_prediction_csv(result: dict[str, Any], path: Path) -> None:
    rows = result.get("rows", [])
    if not rows:
        raise ValueError("저장할 예측 결과가 없습니다.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_default_sample_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(DEFAULT_SAMPLE_ROWS[0].keys()))
        writer.writeheader()
        writer.writerows(DEFAULT_SAMPLE_ROWS)
    return path


def lite_sample_csv_path(create_if_missing: bool = True) -> Path:
    candidates: list[Path] = []
    for root in runtime_roots():
        candidates.extend(
            [
                root / "samples" / "company_sensor_sample.csv",
                root / "sample_company_sensor.csv",
            ]
        )
    for path in candidates:
        if path.exists():
            return path

    target_root = runtime_roots()[0] if runtime_roots() else PROJECT_ROOT
    target = target_root / "samples" / "company_sensor_sample.csv"
    if create_if_missing:
        return write_default_sample_csv(target)
    return target


def init_db(db_path: Path = LITE_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS lite_workflow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )


def insert_record(record_type: str, payload: dict[str, Any], db_path: Path = LITE_DB) -> dict[str, Any]:
    init_db(db_path)
    record = dict(payload)
    record["record_id"] = record.get("record_id") or str(uuid.uuid4())
    record["record_type"] = record_type
    record["created_at"] = record.get("created_at") or now_iso()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO lite_workflow (record_id, record_type, created_at, payload_json) VALUES (?, ?, ?, ?)",
            (record["record_id"], record_type, record["created_at"], json.dumps(record, ensure_ascii=False)),
        )
    return record


def list_records(record_type: str, limit: int = 20, db_path: Path = LITE_DB) -> list[dict[str, Any]]:
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT payload_json FROM lite_workflow
            WHERE record_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (record_type, int(limit)),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def create_event(sensor_row: dict[str, Any]) -> dict[str, Any]:
    score = score_row(sensor_row)
    return insert_record(
        "event",
        {
            "equipment_id": sensor_row.get("equipment_id", "EQ-001"),
            "sensor_row": sensor_row,
            **score,
        },
    )


def create_draft(event: dict[str, Any]) -> dict[str, Any]:
    return insert_record(
        "draft",
        {
            "event_id": event["record_id"],
            "risk_status": event["risk_status"],
            "failure_probability": event["failure_probability"],
            "key_signals": event["key_signals"],
            "draft_text": f"{event.get('equipment_id', '설비')}의 주요 위험 신호({event['key_signals']})를 확인하세요.",
        },
    )


def create_decision(draft: dict[str, Any], decision: str, note: str = "") -> dict[str, Any]:
    return insert_record(
        "decision",
        {
            "draft_id": draft["record_id"],
            "event_id": draft["event_id"],
            "decision": decision,
            "note": note,
        },
    )


def infer_provider(api_key: str) -> str:
    key = api_key.strip()
    if key.startswith("AIza"):
        return "gemini"
    if key.startswith("sk-"):
        return "openai"
    raise ValueError("지원하지 않는 API key 형식입니다. Gemini 또는 OpenAI key를 사용하세요.")


def generate_ai_report(api_key: str, summary: dict[str, Any]) -> tuple[str, str]:
    provider = infer_provider(api_key)
    prompt = (
        "Write a concise predictive maintenance manager report in Korean. "
        f"Rows={summary.get('row_count')}, high risk={summary.get('high_risk_count')}, "
        f"max probability={summary.get('max_probability')}. "
        "Mention that this is advisory and requires human approval."
    )
    if provider == "gemini":
        last_error: Exception | None = None
        for model in ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
            payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 500}}
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = json.loads(response.read().decode("utf-8"))
                text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text, f"gemini_generate_content:{model}"
            except Exception as error:
                last_error = error
        raise RuntimeError(f"Gemini report generation failed for all free-tier candidates: {last_error}")

    model = "gpt-5-mini"
    payload = {
        "model": model,
        "input": prompt,
        "max_output_tokens": 500,
        "truncation": "auto",
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    output_text = []
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                output_text.append(content.get("text", ""))
    return "\n".join(output_text).strip(), f"openai_responses_api:{model}"


def lite_smoke_test() -> dict[str, Any]:
    path = lite_sample_csv_path()
    return predict_csv(path)
