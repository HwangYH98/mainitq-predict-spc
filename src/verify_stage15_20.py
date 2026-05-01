import json
import uuid
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api_server import app
from operations_store import (
    DEFAULT_DB_PATH,
    get_prediction_event,
    list_prediction_events,
    list_work_order_drafts,
)
from realtime_ops import (
    ARCHITECTURE_PATH,
    INCOMING_DIR,
    PROCESSED_DIR,
    scan_realtime_folder,
    write_stage15_20_architecture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"


def pass_step(message: str) -> None:
    print(f"[OK] {message}")


def require_file(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"Missing required file: {path}")
    if path.is_file() and path.stat().st_size <= 0:
        raise AssertionError(f"File is empty: {path}")


def sample_sensor_row() -> dict:
    """Use one AI4I row as a realistic incoming sensor payload."""
    df = pd.read_csv(DATA_PATH)
    high_risk_like = df[df["Machine failure"] == 1]
    row = high_risk_like.iloc[0] if not high_risk_like.empty else df.iloc[0]
    columns = [
        "Type",
        "Air temperature [K]",
        "Process temperature [K]",
        "Rotational speed [rpm]",
        "Torque [Nm]",
        "Tool wear [min]",
    ]
    return row[columns].to_dict()


def verify_file_drop_streaming(row: dict) -> str:
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    incoming_csv = INCOMING_DIR / f"verify_stage15_stream_{uuid.uuid4().hex[:8]}.csv"
    pd.DataFrame([row]).to_csv(incoming_csv, index=False, encoding="utf-8-sig")

    events = scan_realtime_folder(INCOMING_DIR, db_path=DEFAULT_DB_PATH)
    if len(events) != 1:
        raise AssertionError(f"Expected 1 file-drop event, found {len(events)}")
    if get_prediction_event(events[0]["event_id"]) is None:
        raise AssertionError("File-drop event was not persisted to SQLite.")
    if incoming_csv.exists():
        raise AssertionError("Incoming stream CSV was not moved out of the incoming folder.")

    processed_csv = PROCESSED_DIR / incoming_csv.name
    require_file(processed_csv)

    pass_step(
        "Stage 15-lite file-drop streaming passed "
        f"(event {events[0]['event_id']}, risk {events[0]['risk_status']})."
    )
    return events[0]["event_id"]


def verify_fastapi(row: dict) -> list[str]:
    client = TestClient(app)

    health = client.get("/health")
    if health.status_code != 200 or health.json()["status"] != "ok":
        raise AssertionError(f"/health failed: {health.status_code} {health.text}")

    model_info = client.get("/model-info")
    if model_info.status_code != 200 or model_info.json()["feature_count"] <= 0:
        raise AssertionError(f"/model-info failed: {model_info.status_code} {model_info.text}")

    prediction = client.post("/predict", json={"row": row, "source": "verify_api", "persist": True})
    if prediction.status_code != 200:
        raise AssertionError(f"/predict failed: {prediction.status_code} {prediction.text}")
    event = prediction.json()
    if "event_id" not in event or "probability" not in event:
        raise AssertionError("/predict response is missing event_id or probability.")

    batch = client.post("/predict-batch", json={"rows": [row], "source": "verify_batch", "persist": True})
    if batch.status_code != 200 or batch.json()["count"] != 1:
        raise AssertionError(f"/predict-batch failed: {batch.status_code} {batch.text}")
    batch_event = batch.json()["events"][0]

    events = client.get("/events?limit=5")
    if events.status_code != 200 or not events.json()["events"]:
        raise AssertionError(f"/events failed: {events.status_code} {events.text}")

    pass_step("Stage 16-lite FastAPI endpoints passed.")
    return [event["event_id"], batch_event["event_id"]]


def verify_sqlite_storage(event_ids: list[str]) -> None:
    require_file(DEFAULT_DB_PATH)
    for event_id in event_ids:
        if get_prediction_event(event_id) is None:
            raise AssertionError(f"Prediction event was not persisted to SQLite: {event_id}")

    events = list_prediction_events(limit=10, db_path=DEFAULT_DB_PATH)
    if len(events) < len(event_ids):
        raise AssertionError("SQLite event history has fewer events than expected.")

    pass_step(
        "Stage 17-lite SQLite event storage passed "
        f"({len(events)} recent events checked)."
    )


def verify_work_order(event_id: str) -> None:
    client = TestClient(app)
    response = client.post("/work-order-draft", json={"event_id": event_id})
    if response.status_code != 200:
        raise AssertionError(f"/work-order-draft failed: {response.status_code} {response.text}")

    draft = response.json()
    draft_json = draft["draft_json"]
    if draft_json.get("requires_human_approval") is not True:
        raise AssertionError("Work-order draft must require human approval.")
    if not draft_json.get("evidence"):
        raise AssertionError("Work-order draft is missing evidence.")

    require_file(Path(draft["draft_path"]))
    draft_text = Path(draft["draft_path"]).read_text(encoding="utf-8")
    if "\ufffd" in draft_text:
        raise AssertionError("Work-order draft contains a UTF-8 replacement character.")
    if "Stage 18-lite 작업지시 초안" not in draft_text:
        raise AssertionError("Work-order draft title is missing or corrupted.")

    drafts = list_work_order_drafts(limit=5, db_path=DEFAULT_DB_PATH)
    if not drafts:
        raise AssertionError("Work-order draft was not persisted to SQLite.")

    pass_step(f"Stage 18-lite work-order draft passed ({draft['draft_id']}).")


def main() -> None:
    print(f"Verifying Stage 15~18-lite local operations at: {PROJECT_ROOT}")
    require_file(DATA_PATH)
    write_stage15_20_architecture()
    require_file(ARCHITECTURE_PATH)

    row = sample_sensor_row()
    event_ids = [verify_file_drop_streaming(row)]
    event_ids.extend(verify_fastapi(row))
    verify_sqlite_storage(event_ids)
    event_id = event_ids[1]
    verify_work_order(event_id)

    events = list_prediction_events(limit=10)
    if not events:
        raise AssertionError("No prediction events found after verification.")

    db_summary = {
        "operations_db": str(DEFAULT_DB_PATH),
        "event_count_checked": len(events),
        "latest_event_id": events[0]["event_id"],
    }
    print(json.dumps(db_summary, ensure_ascii=False, indent=2))
    print("All Stage 15~18-lite local operations checks passed.")


if __name__ == "__main__":
    main()
