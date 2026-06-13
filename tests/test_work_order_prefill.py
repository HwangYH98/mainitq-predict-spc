from __future__ import annotations

from datetime import datetime

from work_order_prefill import prediction_row_to_work_order_prefill


def test_prefill_prefers_explicit_equipment_identifier() -> None:
    prefill = prediction_row_to_work_order_prefill(
        {
            "input_row": 7,
            "equipment_id": "PRESS-09",
            "machine_id": "MACHINE-02",
            "timestamp": "2026-06-13T10:00:00+09:00",
            "Type": "L",
            "Air temperature [K]": 303.8,
            "Process temperature [K]": 313.2,
            "Rotational speed [rpm]": 1350,
            "Torque [Nm]": 62.0,
            "Tool wear [min]": 210,
        }
    )

    assert prefill["equipment_id"] == "PRESS-09"
    assert prefill["event_timestamp"] == "2026-06-13T10:00:00+09:00"
    assert prefill["source_system"] == "prediction_monitoring_selection"
    assert prefill["sensor_row"] == {
        "Type": "L",
        "Air temperature [K]": 303.8,
        "Process temperature [K]": 313.2,
        "Rotational speed [rpm]": 1350,
        "Torque [Nm]": 62.0,
        "Tool wear [min]": 210,
    }


def test_prefill_falls_back_to_input_row_identifier() -> None:
    prefill = prediction_row_to_work_order_prefill(
        {
            "input_row": 42,
            "Type": "bad",
            "Air temperature [K]": "not numeric",
        }
    )

    assert prefill["equipment_id"] == "input_row-42"
    assert prefill["sensor_row"]["Type"] == "M"
    assert prefill["sensor_row"]["Air temperature [K]"] == 298.1


def test_prefill_does_not_use_time_step_as_event_timestamp() -> None:
    prefill = prediction_row_to_work_order_prefill(
        {
            "input_row": 7593,
            "time_step": 7593,
            "Type": "H",
            "Air temperature [K]": 302.1,
            "Process temperature [K]": 312.7,
        }
    )

    assert prefill["equipment_id"] == "input_row-7593"
    assert prefill["event_timestamp"] != "7593"
    datetime.fromisoformat(prefill["event_timestamp"])


def test_prefill_ignores_invalid_timestamp_candidate() -> None:
    prefill = prediction_row_to_work_order_prefill(
        {
            "asset_id": "CUTTER-01",
            "timestamp": "7593",
            "simulated_timestamp": "2026-06-13T15:20:00+09:00",
        }
    )

    assert prefill["equipment_id"] == "CUTTER-01"
    assert prefill["event_timestamp"] == "2026-06-13T15:20:00+09:00"
