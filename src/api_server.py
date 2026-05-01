import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from operations_store import (
    get_prediction_event,
    list_prediction_events,
    list_work_order_decisions,
)
from realtime_ops import (
    ALLOWED_WORK_ORDER_DECISIONS,
    create_work_order_decision,
    create_work_order_draft,
    load_realtime_model_bundle,
    predict_field_event,
    predict_sensor_row,
    predict_sensor_rows,
)


app = FastAPI(
    title="Predictive SPC Stage 1~20 Local Integration API",
    description=(
        "Local PoC API for AI4I-compatible sensor prediction, field-event "
        "integration, SQLite event history, and human-approved work-order decisions."
    ),
    version="0.2.0",
)


class PredictRequest(BaseModel):
    row: dict[str, Any] = Field(..., description="One AI4I-compatible sensor row.")
    source: str = "api"
    persist: bool = True


class BatchPredictRequest(BaseModel):
    rows: list[dict[str, Any]]
    source: str = "api_batch"
    persist: bool = True


class WorkOrderDraftRequest(BaseModel):
    event_id: str


class FieldEventRequest(BaseModel):
    equipment_id: str = Field(..., description="Local equipment or asset id.")
    event_timestamp: str = Field(..., description="ISO-8601 timestamp from the source system.")
    source_system: str = Field(..., description="Example: csv_drop, mes_export, opcua_bridge.")
    row: dict[str, Any] = Field(..., description="One AI4I-compatible sensor row.")
    persist: bool = True


class WorkOrderDecisionRequest(BaseModel):
    draft_id: str
    decision: str = Field(..., description=f"One of: {', '.join(sorted(ALLOWED_WORK_ORDER_DECISIONS))}.")
    operator_id: str = "local_demo_operator"
    note: str = ""


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "stage1_20_local_integration_api"}


@app.get("/model-info")
def model_info() -> dict:
    _, feature_columns, _, threshold = load_realtime_model_bundle()
    return {
        "model_name": "xgboost_ai4i_realtime_lite",
        "threshold": threshold,
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "scope": "Stage 1~20 local PoC API for AI4I-compatible rows",
    }


@app.post("/predict")
def predict(request: PredictRequest) -> dict:
    try:
        return predict_sensor_row(
            request.row,
            source=request.source,
            persist=request.persist,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/predict-batch")
def predict_batch(request: BatchPredictRequest) -> dict:
    try:
        events = predict_sensor_rows(
            request.rows,
            source=request.source,
            persist=request.persist,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"count": len(events), "events": events}


@app.get("/events")
def events(limit: int = 50) -> dict:
    return {"events": list_prediction_events(limit=limit)}


@app.post("/field-event")
def field_event(request: FieldEventRequest) -> dict:
    try:
        return predict_field_event(
            equipment_id=request.equipment_id,
            event_timestamp=request.event_timestamp,
            source_system=request.source_system,
            row=request.row,
            persist=request.persist,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/work-order-draft")
def work_order_draft(request: WorkOrderDraftRequest) -> dict:
    event = get_prediction_event(request.event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Prediction event not found: {request.event_id}")
    return create_work_order_draft(event)


@app.post("/work-order-decision")
def work_order_decision(request: WorkOrderDecisionRequest) -> dict:
    try:
        return create_work_order_decision(
            draft_id=request.draft_id,
            decision=request.decision,
            operator_id=request.operator_id,
            note=request.note,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/work-order-decisions")
def work_order_decisions(limit: int = 50) -> dict:
    return {"decisions": list_work_order_decisions(limit=limit)}
