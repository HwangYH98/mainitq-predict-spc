from __future__ import annotations

from pathlib import Path

from operations_store import (
    get_prediction_event,
    get_work_order_draft,
    initialize_db,
    insert_prediction_event,
    insert_work_order_decision,
    insert_work_order_draft,
    list_work_order_decisions,
)


def test_prediction_draft_decision_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "operations.db"
    initialize_db(db_path)

    event = {
        "event_id": "event-1",
        "source": "pytest",
        "created_at": "2026-05-09T00:00:00+09:00",
        "model_name": "xgboost",
        "probability": 0.91,
        "threshold": 0.87,
        "risk_status": "High Risk",
        "input": {"equipment_id": "EQ-001"},
        "top_shap_factors": [{"feature": "Tool wear [min]", "value": 0.4}],
    }
    insert_prediction_event(event, db_path)
    saved_event = get_prediction_event("event-1", db_path)
    assert saved_event is not None
    assert saved_event["risk_status"] == "High Risk"

    draft = {
        "draft_id": "draft-1",
        "event_id": "event-1",
        "created_at": "2026-05-09T00:01:00+09:00",
        "generation_mode": "template",
        "draft_json": {"recommended_action": "inspection"},
        "markdown": "Inspect the equipment.",
        "draft_path": "outputs/work_order_drafts/draft-1.md",
    }
    insert_work_order_draft(draft, db_path)
    saved_draft = get_work_order_draft("draft-1", db_path)
    assert saved_draft is not None
    assert saved_draft["event_id"] == "event-1"

    decision = {
        "decision_id": "decision-1",
        "draft_id": "draft-1",
        "event_id": "event-1",
        "created_at": "2026-05-09T00:02:00+09:00",
        "operator_id": "operator",
        "decision": "needs_review",
        "note": "Keep this row as a retraining candidate.",
    }
    insert_work_order_decision(decision, db_path)
    decisions = list_work_order_decisions(db_path=db_path)
    assert decisions[0]["decision"] == "needs_review"
    assert decisions[0]["draft_id"] == "draft-1"
