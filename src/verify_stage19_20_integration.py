import os
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api_server import app
from operations_store import (
    DEFAULT_DB_PATH,
    get_prediction_event,
    list_work_order_decisions,
)
from predictive_spc import genai_ai_report
from realtime_ops import WORK_ORDER_DECISIONS_PATH, write_stage15_20_architecture


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"


def pass_step(message: str) -> None:
    print(f"[OK] {message}")


def require_file(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"Missing required file: {path}")
    if path.is_file() and path.stat().st_size <= 0:
        raise AssertionError(f"File is empty: {path}")


def json_ready(value):
    """Convert pandas/numpy values into plain Python values for TestClient JSON."""
    if hasattr(value, "item"):
        return value.item()
    return value


def sample_sensor_row() -> dict:
    """Use one failure-like AI4I row as a realistic field event payload."""
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
    return {column: json_ready(row[column]) for column in columns}


def verify_missing_genai_key_fails() -> None:
    """GenAI-required mode should fail clearly without an API key."""
    old_provider = os.environ.get("AI_REPORT_PROVIDER")
    old_key = os.environ.pop("GEMINI_API_KEY", None)
    try:
        os.environ["AI_REPORT_PROVIDER"] = "gemini"
        try:
            genai_ai_report({}, require_genai=True)
        except RuntimeError as error:
            if "GEMINI_API_KEY is required" not in str(error):
                raise AssertionError(f"Unexpected Gemini error text: {error}") from error
        else:
            raise AssertionError("require_genai=True should fail when GEMINI_API_KEY is missing.")
    finally:
        if old_provider is None:
            os.environ.pop("AI_REPORT_PROVIDER", None)
        else:
            os.environ["AI_REPORT_PROVIDER"] = old_provider
        if old_key is not None:
            os.environ["GEMINI_API_KEY"] = old_key
    pass_step("GenAI-required mode fails clearly when GEMINI_API_KEY is missing.")


def verify_field_event(client: TestClient, row: dict) -> str:
    response = client.post(
        "/field-event",
        json={
            "equipment_id": "press-01",
            "event_timestamp": "2026-06-01T08:00:00+09:00",
            "source_system": "local_field_bridge",
            "row": row,
            "persist": True,
        },
    )
    if response.status_code != 200:
        raise AssertionError(f"/field-event failed: {response.status_code} {response.text}")

    event = response.json()
    for key in ["event_id", "probability", "risk_status", "field_event"]:
        if key not in event:
            raise AssertionError(f"/field-event response is missing key: {key}")
    if event["field_event"]["equipment_id"] != "press-01":
        raise AssertionError("/field-event did not echo the equipment_id.")
    if not event["source"].startswith("field_event:"):
        raise AssertionError("/field-event should store a field_event source string.")
    if get_prediction_event(event["event_id"], db_path=DEFAULT_DB_PATH) is None:
        raise AssertionError("Stage 19 field event was not persisted to SQLite.")

    pass_step(f"Stage 19 /field-event passed ({event['event_id']}).")
    return event["event_id"]


def verify_work_order_decision(client: TestClient, event_id: str) -> str:
    draft_response = client.post("/work-order-draft", json={"event_id": event_id})
    if draft_response.status_code != 200:
        raise AssertionError(
            f"/work-order-draft failed: {draft_response.status_code} {draft_response.text}"
        )
    draft = draft_response.json()
    draft_id = draft["draft_id"]

    decision_response = client.post(
        "/work-order-decision",
        json={
            "draft_id": draft_id,
            "decision": "needs_review",
            "operator_id": "stage20_local_operator",
            "note": "Verified during Stage 19~20 local integration smoke test.",
        },
    )
    if decision_response.status_code != 200:
        raise AssertionError(
            "/work-order-decision failed: "
            f"{decision_response.status_code} {decision_response.text}"
        )
    decision = decision_response.json()
    if decision["draft_id"] != draft_id or decision["decision"] != "needs_review":
        raise AssertionError("/work-order-decision returned the wrong draft or decision.")

    decisions = list_work_order_decisions(limit=10, db_path=DEFAULT_DB_PATH)
    if not any(item["decision_id"] == decision["decision_id"] for item in decisions):
        raise AssertionError("Stage 20 decision was not persisted to SQLite.")
    require_file(WORK_ORDER_DECISIONS_PATH)
    decisions_csv = pd.read_csv(WORK_ORDER_DECISIONS_PATH)
    if decision["decision_id"] not in decisions_csv["decision_id"].astype(str).tolist():
        raise AssertionError("Stage 20 decision was not exported to work_order_decisions.csv.")

    pass_step(f"Stage 20 /work-order-decision passed ({decision['decision_id']}).")
    return decision["decision_id"]


def verify_negative_cases(client: TestClient) -> None:
    invalid_field = client.post(
        "/field-event",
        json={
            "equipment_id": "press-01",
            "event_timestamp": "not-a-timestamp",
            "source_system": "local_field_bridge",
            "row": {"Torque [Nm]": 60},
        },
    )
    if invalid_field.status_code != 400:
        raise AssertionError(f"Invalid /field-event should return 400, got {invalid_field.status_code}.")

    missing_draft = client.post(
        "/work-order-decision",
        json={"draft_id": "missing-draft-id", "decision": "approve"},
    )
    if missing_draft.status_code != 404:
        raise AssertionError(
            f"Missing draft /work-order-decision should return 404, got {missing_draft.status_code}."
        )

    invalid_decision = client.post(
        "/work-order-decision",
        json={"draft_id": "missing-draft-id", "decision": "ship_it"},
    )
    if invalid_decision.status_code != 400:
        raise AssertionError(
            f"Invalid decision should return 400 before lookup, got {invalid_decision.status_code}."
        )

    pass_step("Negative Stage 19~20 API cases returned friendly errors.")


def main() -> None:
    print(f"Verifying Stage 19~20 local integration at: {PROJECT_ROOT}")
    require_file(DATA_PATH)
    write_stage15_20_architecture()
    verify_missing_genai_key_fails()

    client = TestClient(app)
    row = sample_sensor_row()
    event_id = verify_field_event(client, row)
    verify_work_order_decision(client, event_id)
    verify_negative_cases(client)

    summary = {
        "operations_db": str(DEFAULT_DB_PATH),
        "decisions_csv": str(WORK_ORDER_DECISIONS_PATH),
    }
    print(summary)
    print("All Stage 19~20 local integration checks passed.")


if __name__ == "__main__":
    main()
