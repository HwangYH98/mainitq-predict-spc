from __future__ import annotations

from datetime import datetime, timezone
import json
from functools import lru_cache
from pathlib import Path
import shutil
import uuid

import numpy as np
import pandas as pd

from data import preprocess_features, prepare_train_test_data
from operations_store import (
    DEFAULT_DB_PATH,
    get_work_order_draft,
    insert_prediction_event,
    insert_work_order_decision,
    insert_work_order_draft,
)
from train_baseline import RANDOM_STATE, TEST_SIZE, build_models


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
THRESHOLD_PATH = OUTPUT_DIR / "threshold_summary.json"
REALTIME_DIR = OUTPUT_DIR / "realtime_stream"
INCOMING_DIR = REALTIME_DIR / "incoming"
PROCESSED_DIR = REALTIME_DIR / "processed"
EVENTS_CSV_PATH = REALTIME_DIR / "latest_events.csv"
WORK_ORDER_DIR = OUTPUT_DIR / "work_order_drafts"
WORK_ORDER_DECISIONS_PATH = OUTPUT_DIR / "work_order_decisions.csv"
ARCHITECTURE_PATH = OUTPUT_DIR / "stage15_20_architecture.md"
ALLOWED_WORK_ORDER_DECISIONS = {"approve", "reject", "needs_review"}


def now_iso() -> str:
    """Return a compact UTC timestamp for event records."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_safe(value):
    """Convert pandas/numpy objects into JSON-safe values."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def read_selected_threshold() -> float:
    """Read the Stage 4-lite selected threshold, with a safe fallback."""
    if not THRESHOLD_PATH.exists():
        return 0.5
    payload = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
    return float(payload.get("selected_threshold", 0.5))


@lru_cache(maxsize=1)
def load_realtime_model_bundle() -> tuple[object, list[str], object, float]:
    """
    Train the same XGBoost baseline used by the dashboard for local API inference.

    This is still a local PoC model, not a production model registry.
    """
    import shap

    X_train, _, y_train, _, _ = prepare_train_test_data(
        csv_path=DATA_PATH,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )
    model = build_models(y_train)["xgboost"]
    model.fit(X_train, y_train)
    explainer = shap.TreeExplainer(model)
    return model, list(X_train.columns), explainer, read_selected_threshold()


def top_shap_factors(features: pd.DataFrame, shap_values: np.ndarray, limit: int = 5) -> list[dict]:
    """Return compact SHAP evidence for one predicted row."""
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    row_shap = pd.Series(shap_values[0], index=features.columns)
    row_values = features.iloc[0]
    top = row_shap.abs().sort_values(ascending=False).head(limit)
    factors = []
    for feature_name in top.index:
        factors.append(
            {
                "feature": str(feature_name),
                "value": json_safe(row_values[feature_name]),
                "shap_value": round(float(row_shap[feature_name]), 6),
                "direction": "toward_failure" if row_shap[feature_name] > 0 else "toward_normal",
            }
        )
    return factors


def predict_sensor_row(
    row: dict,
    source: str = "api",
    persist: bool = True,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict:
    """Predict one AI4I-style sensor row and optionally store it in SQLite."""
    model, feature_columns, explainer, selected_threshold = load_realtime_model_bundle()
    raw_df = pd.DataFrame([row])
    features = preprocess_features(raw_df, expected_columns=feature_columns)
    probability = float(model.predict_proba(features)[:, 1][0])
    risk_status = "High Risk" if probability >= selected_threshold else "Normal"
    shap_values = explainer.shap_values(features)
    factors = top_shap_factors(features, shap_values)

    event = {
        "event_id": str(uuid.uuid4()),
        "source": source,
        "created_at": now_iso(),
        "model_name": "xgboost_ai4i_realtime_lite",
        "probability": round(probability, 6),
        "threshold": round(selected_threshold, 6),
        "risk_status": risk_status,
        "input": json_safe(row),
        "top_shap_factors": factors,
        "schema_note": "AI4I-compatible row expected for Stage 15~18-lite local API inference.",
    }
    if persist:
        insert_prediction_event(event, db_path=db_path)
    return event


def predict_sensor_rows(
    rows: list[dict],
    source: str = "api_batch",
    persist: bool = True,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Predict a batch of sensor rows."""
    return [
        predict_sensor_row(row, source=source, persist=persist, db_path=db_path)
        for row in rows
    ]


def validate_field_event_metadata(
    equipment_id: str,
    event_timestamp: str,
    source_system: str,
) -> None:
    """Fail early when Stage 19 field-event metadata is not usable."""
    if not equipment_id.strip():
        raise ValueError("equipment_id is required for a field event.")
    if not source_system.strip():
        raise ValueError("source_system is required for a field event.")
    if not event_timestamp.strip():
        raise ValueError("event_timestamp is required for a field event.")

    timestamp_text = event_timestamp.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(timestamp_text)
    except ValueError as error:
        raise ValueError(
            "event_timestamp must be an ISO-8601 timestamp, for example "
            "2026-06-01T08:00:00+09:00."
        ) from error


def predict_field_event(
    equipment_id: str,
    event_timestamp: str,
    source_system: str,
    row: dict,
    persist: bool = True,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict:
    """
    Process one Stage 19 field event through the same local prediction pipeline.

    This is a local integration contract: external factory connectors can map
    PLC/SCADA/MES rows into this payload shape later.
    """
    validate_field_event_metadata(equipment_id, event_timestamp, source_system)
    enriched_row = dict(row)
    enriched_row.update(
        {
            "equipment_id": equipment_id,
            "event_timestamp": event_timestamp,
            "source_system": source_system,
        }
    )
    source = f"field_event:{source_system}:{equipment_id}"
    event = predict_sensor_row(enriched_row, source=source, persist=persist, db_path=db_path)
    event["field_event"] = {
        "equipment_id": equipment_id,
        "event_timestamp": event_timestamp,
        "source_system": source_system,
    }
    if persist:
        append_events_artifact([event])
    return event


def append_events_artifact(events: list[dict], path: str | Path = EVENTS_CSV_PATH) -> None:
    """Write a dashboard-readable CSV of the latest simulated stream events."""
    if not events:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for event in events:
        event_input = event.get("input", {})
        rows.append(
            {
                "event_id": event["event_id"],
                "created_at": event["created_at"],
                "source": event["source"],
                "equipment_id": event_input.get("equipment_id", ""),
                "event_timestamp": event_input.get("event_timestamp", ""),
                "source_system": event_input.get("source_system", ""),
                "model_name": event["model_name"],
                "probability": event["probability"],
                "threshold": event["threshold"],
                "risk_status": event["risk_status"],
                "top_factor": event["top_shap_factors"][0]["feature"]
                if event["top_shap_factors"]
                else "",
            }
        )

    new_df = pd.DataFrame(rows)
    if path.exists():
        old_df = pd.read_csv(path)
        new_df = pd.concat([old_df, new_df], ignore_index=True)
    new_df.to_csv(path, index=False, encoding="utf-8-sig")


def process_stream_file(
    csv_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    move_processed: bool = True,
) -> list[dict]:
    """Process one incoming CSV as a file-drop streaming simulation."""
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)
    events = []
    for _, row in df.iterrows():
        events.append(
            predict_sensor_row(
                row.to_dict(),
                source=f"file_drop:{csv_path.name}",
                persist=True,
                db_path=db_path,
            )
        )

    append_events_artifact(events)

    if move_processed:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        destination = PROCESSED_DIR / csv_path.name
        if destination.exists():
            destination = PROCESSED_DIR / f"{csv_path.stem}_{uuid.uuid4().hex[:8]}{csv_path.suffix}"
        shutil.move(str(csv_path), str(destination))

    return events


def scan_realtime_folder(
    incoming_dir: str | Path = INCOMING_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Process every CSV currently waiting in the incoming folder."""
    incoming_dir = Path(incoming_dir)
    incoming_dir.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_events = []
    for csv_path in sorted(incoming_dir.glob("*.csv")):
        all_events.extend(process_stream_file(csv_path, db_path=db_path, move_processed=True))
    return all_events


def work_order_actions(event: dict) -> list[str]:
    """Build conservative manager-review actions from SHAP evidence."""
    actions = [
        "Confirm the sensor row and compare it with recent normal operating conditions.",
        "Review the top SHAP factors before deciding any maintenance action.",
    ]
    feature_text = " ".join(factor["feature"] for factor in event.get("top_shap_factors", []))
    if "torque" in feature_text:
        actions.append("Inspect torque-related load, bearing condition, and shaft alignment.")
    if "tool_wear" in feature_text or "wear" in feature_text:
        actions.append("Check tool wear age and replacement schedule.")
    if "temperature" in feature_text or "temp" in feature_text:
        actions.append("Check cooling condition and abnormal temperature drift.")
    if event.get("risk_status") == "High Risk":
        actions.append("Escalate to a human manager for inspection approval before work starts.")
    return actions


def create_work_order_draft(
    event: dict,
    db_path: str | Path = DEFAULT_DB_PATH,
    output_dir: str | Path = WORK_ORDER_DIR,
) -> dict:
    """Create a human-approval work-order draft as JSON and Markdown."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    draft_id = str(uuid.uuid4())
    created_at = now_iso()
    risk_level = "High" if event.get("risk_status") == "High Risk" else "Watch"
    evidence = {
        "event_id": event["event_id"],
        "probability": event["probability"],
        "threshold": event["threshold"],
        "risk_status": event["risk_status"],
        "top_shap_factors": event.get("top_shap_factors", []),
    }
    draft_json = {
        "draft_id": draft_id,
        "event_id": event["event_id"],
        "risk_level": risk_level,
        "evidence": evidence,
        "recommended_actions": work_order_actions(event),
        "requires_human_approval": True,
        "guardrail": "This is a manager approval draft, not an automatic maintenance command.",
    }
    action_lines = "\n".join(
        f"{index}. {action}"
        for index, action in enumerate(draft_json["recommended_actions"], start=1)
    )
    factor_lines = "\n".join(
        f"- {factor['feature']}: SHAP {factor['shap_value']} ({factor['direction']})"
        for factor in event.get("top_shap_factors", [])
    )
    markdown = (
        "# Stage 18-lite 작업지시 초안\n\n"
        f"- Draft ID: `{draft_id}`\n"
        f"- Event ID: `{event['event_id']}`\n"
        f"- Risk level: `{risk_level}`\n"
        f"- Failure probability: `{event['probability']}`\n"
        f"- Threshold: `{event['threshold']}`\n"
        f"- Human approval required: `true`\n\n"
        "## Evidence\n\n"
        f"{factor_lines or '- No SHAP factors available.'}\n\n"
        "## Recommended Actions\n\n"
        f"{action_lines}\n\n"
        "## Guardrail\n\n"
        "This draft is a manager approval document. It must not be treated as an "
        "automatic maintenance command.\n"
    )
    draft_path = output_dir / f"work_order_{draft_id}.md"
    draft_path.write_text(markdown, encoding="utf-8")

    payload = {
        "draft_id": draft_id,
        "event_id": event["event_id"],
        "created_at": created_at,
        "generation_mode": "structured_template_human_approval",
        "draft_json": draft_json,
        "markdown": markdown,
        "draft_path": str(draft_path),
    }
    insert_work_order_draft(payload, db_path=db_path)
    return payload


def append_decisions_artifact(
    decisions: list[dict],
    path: str | Path = WORK_ORDER_DECISIONS_PATH,
) -> None:
    """Write a dashboard-readable CSV of Stage 20 operator decisions."""
    if not decisions:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "decision_id": decision["decision_id"],
            "draft_id": decision["draft_id"],
            "event_id": decision["event_id"],
            "created_at": decision["created_at"],
            "operator_id": decision["operator_id"],
            "decision": decision["decision"],
            "note": decision["note"],
        }
        for decision in decisions
    ]
    new_df = pd.DataFrame(rows)
    if path.exists():
        old_df = pd.read_csv(path)
        new_df = pd.concat([old_df, new_df], ignore_index=True)
    new_df.to_csv(path, index=False, encoding="utf-8-sig")


def create_work_order_decision(
    draft_id: str,
    decision: str,
    operator_id: str = "local_demo_operator",
    note: str = "",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict:
    """Record a Stage 20 human decision for a generated work-order draft."""
    normalized_decision = decision.strip().lower()
    if normalized_decision not in ALLOWED_WORK_ORDER_DECISIONS:
        allowed = ", ".join(sorted(ALLOWED_WORK_ORDER_DECISIONS))
        raise ValueError(f"decision must be one of: {allowed}")
    if not operator_id.strip():
        raise ValueError("operator_id is required.")

    draft = get_work_order_draft(draft_id, db_path=db_path)
    if draft is None:
        raise LookupError(f"Work-order draft not found: {draft_id}")

    payload = {
        "decision_id": str(uuid.uuid4()),
        "draft_id": draft_id,
        "event_id": draft["event_id"],
        "created_at": now_iso(),
        "operator_id": operator_id,
        "decision": normalized_decision,
        "note": note,
        "requires_human_approval": True,
        "guardrail": "Stage 20 records a human decision. It is not an automatic maintenance command.",
    }
    insert_work_order_decision(payload, db_path=db_path)
    append_decisions_artifact([payload])
    return payload


def write_stage15_20_architecture(path: str | Path = ARCHITECTURE_PATH) -> Path:
    """Write the thesis-safe Stage 15~20 architecture note."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# Stage 15~20 확장 아키텍처

## 구현된 local PoC 범위

- Stage 15-lite: `outputs/realtime_stream/incoming` 폴더에 들어온 CSV를 file-drop streaming simulation으로 처리한다.
- Stage 16-lite: FastAPI 서버가 `POST /predict`, `POST /predict-batch`, `GET /health`, `GET /model-info`, `GET /events`, `POST /work-order-draft`를 제공한다.
- Stage 17-lite: 예측 event, 고장 확률, risk label, SHAP 근거, 작업지시 초안을 `outputs/operations.db` SQLite DB에 저장한다.
- Stage 18-lite: 자동 정비 명령이 아니라 관리자 승인용 작업지시 초안을 JSON/Markdown으로 생성한다.
- Stage 19-lite: `POST /field-event`로 equipment_id, timestamp, source_system, sensor row를 받아 로컬 예측 이벤트로 저장한다.
- Stage 20-lite: `POST /work-order-decision`으로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록한다.

## 아직 구현하지 않는 외부 운영 범위

- Stage 19 실제 현장 연동은 OPC UA, MQTT, Modbus, SCADA 또는 MES/PLC API가 필요하다.
- Stage 20 운영 시스템화는 로그인, 권한, 알림, 감사 로그, 재학습 관리, 배포 환경, 보안 검토가 필요하다.
- 현재 결과는 Stage 1~20 로컬 통합 PoC이며 실제 공장 배포 완료 또는 무인 자동 정비 실행으로 표현하지 않는다.

## 논문 표현

본 연구는 real-time deployment를 완료한 것이 아니라, file-drop streaming simulation, local FastAPI inference, SQLite event history, human-approved work-order draft, local operator decision logging을 통해 실제 운영 시스템으로 확장 가능한 구조를 검증했다.
""",
        encoding="utf-8",
    )
    return path
