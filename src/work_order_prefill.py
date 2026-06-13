from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


EQUIPMENT_ID_COLUMNS = (
    "equipment_id",
    "machine_id",
    "asset_id",
    "equipment",
    "machine",
    "asset",
    "vehicle_id",
    "UDI",
    "Product ID",
)
TIMESTAMP_COLUMNS = ("event_timestamp", "timestamp", "simulated_timestamp", "time_step")
SENSOR_DEFAULTS = {
    "Type": "M",
    "Air temperature [K]": 298.1,
    "Process temperature [K]": 308.6,
    "Rotational speed [rpm]": 1551,
    "Torque [Nm]": 42.8,
    "Tool wear [min]": 0,
}


def _row_dict(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    if hasattr(row, "to_dict"):
        return dict(row.to_dict())
    return dict(row)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text != "" and text.lower() not in {"nan", "none", "<na>"}


def _lookup(row: Mapping[str, Any], candidates: tuple[str, ...]) -> Any:
    exact = {str(key): value for key, value in row.items()}
    lowered = {str(key).lower(): value for key, value in row.items()}
    for candidate in candidates:
        if candidate in exact and _has_value(exact[candidate]):
            return exact[candidate]
        value = lowered.get(candidate.lower())
        if _has_value(value):
            return value
    return None


def _fallback_equipment_id(row: Mapping[str, Any]) -> str:
    for column in ("input_row", "time_step"):
        value = _lookup(row, (column,))
        if value is not None:
            return f"{column}-{value}"
    return "selected-row"


def _numeric(row: Mapping[str, Any], column: str, default: float) -> float:
    value = _lookup(row, (column,))
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def prediction_row_to_work_order_prefill(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Map one prediction/monitoring row into the work-order event form."""
    values = _row_dict(row)
    equipment_id = _lookup(values, EQUIPMENT_ID_COLUMNS)
    timestamp = _lookup(values, TIMESTAMP_COLUMNS)
    type_value = str(_lookup(values, ("Type",)) or SENSOR_DEFAULTS["Type"]).strip().upper()
    if type_value not in {"L", "M", "H"}:
        type_value = str(SENSOR_DEFAULTS["Type"])

    return {
        "equipment_id": str(equipment_id or _fallback_equipment_id(values)),
        "event_timestamp": str(timestamp or datetime.now().astimezone().replace(microsecond=0).isoformat()),
        "source_system": "prediction_monitoring_selection",
        "sensor_row": {
            "Type": type_value,
            "Air temperature [K]": _numeric(values, "Air temperature [K]", float(SENSOR_DEFAULTS["Air temperature [K]"])),
            "Process temperature [K]": _numeric(values, "Process temperature [K]", float(SENSOR_DEFAULTS["Process temperature [K]"])),
            "Rotational speed [rpm]": int(round(_numeric(values, "Rotational speed [rpm]", float(SENSOR_DEFAULTS["Rotational speed [rpm]"])))),
            "Torque [Nm]": _numeric(values, "Torque [Nm]", float(SENSOR_DEFAULTS["Torque [Nm]"])),
            "Tool wear [min]": int(round(_numeric(values, "Tool wear [min]", float(SENSOR_DEFAULTS["Tool wear [min]"])))),
        },
    }
