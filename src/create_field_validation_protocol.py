from __future__ import annotations

from pathlib import Path
import zipfile

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

PROTOCOL_MD = OUTPUT_DIR / "field_validation_protocol.md"
DATA_TEMPLATE_CSV = OUTPUT_DIR / "field_data_template.csv"
MAINTENANCE_TEMPLATE_CSV = OUTPUT_DIR / "field_maintenance_template.csv"
COST_TEMPLATE_CSV = OUTPUT_DIR / "field_cost_template.csv"
FIELD_VALIDATION_KIT_ZIP = OUTPUT_DIR / "field_validation_data_request_kit.zip"


def create_field_data_template() -> pd.DataFrame:
    """Create the minimum sensor/event template needed for a field validation."""
    return pd.DataFrame(
        [
            {
                "equipment_id": "press-01",
                "timestamp": "2026-05-07T09:00:00+09:00",
                "source_system": "plc_or_scada_export",
                "sensor_schema_version": "v1",
                "air_temperature_k": 298.1,
                "process_temperature_k": 308.6,
                "rotational_speed_rpm": 1551,
                "torque_nm": 42.8,
                "tool_wear_min": 0,
                "actual_failure": 0,
                "failure_timestamp": "",
                "maintenance_action_type": "",
                "work_order_id": "",
                "operator_decision": "",
            },
            {
                "equipment_id": "press-01",
                "timestamp": "2026-05-07T12:00:00+09:00",
                "source_system": "plc_or_scada_export",
                "sensor_schema_version": "v1",
                "air_temperature_k": 302.5,
                "process_temperature_k": 312.2,
                "rotational_speed_rpm": 1280,
                "torque_nm": 68.0,
                "tool_wear_min": 240,
                "actual_failure": 1,
                "failure_timestamp": "2026-05-07T15:30:00+09:00",
                "maintenance_action_type": "component_inspection",
                "work_order_id": "wo-0001",
                "operator_decision": "needs_review",
            },
        ]
    )


def create_field_cost_template() -> pd.DataFrame:
    """Create the minimum maintenance-cost template for before/after validation."""
    return pd.DataFrame(
        [
            {
                "work_order_id": "wo-0001",
                "equipment_id": "press-01",
                "maintenance_start": "2026-05-07T16:00:00+09:00",
                "maintenance_end": "2026-05-07T17:20:00+09:00",
                "downtime_minutes": 80,
                "parts_cost": 150000,
                "labor_cost": 90000,
                "lost_production_cost": 300000,
                "baseline_downtime_minutes": 110,
                "new_policy_downtime_minutes": 80,
                "baseline_detection_delay_minutes": 60,
                "new_policy_detection_delay_minutes": 18,
                "baseline_total_cost": 620000,
                "new_policy_total_cost": 540000,
                "planned_action": 1,
                "false_alarm": 0,
                "missed_failure": 0,
                "baseline_policy": "rule_based_threshold",
                "new_policy": "ml_spc_genai_workflow",
            }
        ]
    )


def create_field_maintenance_template() -> pd.DataFrame:
    """Create the maintenance-history template used to connect alerts to work orders."""
    return pd.DataFrame(
        [
            {
                "work_order_id": "wo-0001",
                "equipment_id": "press-01",
                "maintenance_start": "2026-05-07T16:00:00+09:00",
                "maintenance_end": "2026-05-07T17:20:00+09:00",
                "maintenance_action_type": "component_inspection",
                "failure_type": "tool_wear_overload",
                "technician_id": "tech-01",
                "action_result": "bearing_and_tool_check_completed",
                "linked_alert_timestamp": "2026-05-07T12:00:00+09:00",
                "notes": "sample row; replace with company maintenance history",
            }
        ]
    )


def create_protocol_markdown() -> str:
    """Write a thesis-ready protocol that separates benchmark evidence from field proof."""
    return """# Field Validation Protocol

## Purpose

This protocol defines the data required to prove actual field impact such as
maintenance-cost reduction or earlier failure detection. Public benchmark
results and simulations are useful evidence, but they are not enough to claim
site-specific field savings.

## Required Field Data

| Category | Required fields | Purpose |
|---|---|---|
| Sensor event | equipment_id, timestamp, source_system, sensor values, schema version | Recreate prediction timing and input quality |
| Failure label | actual_failure, failure_timestamp, failure type | Measure missed failures and lead time |
| Maintenance action | work_order_id, action type, operator decision, start/end time | Measure approval flow and MTTR |
| Cost log | parts cost, labor cost, downtime, lost production cost | Compare maintenance cost before/after |
| Baseline policy | previous rule threshold or reactive-maintenance marker | Defines the comparison group |

## Before/After Evaluation

```text
lead_time_minutes = failure_timestamp - first_alert_timestamp
false_alarm_count = predicted_alert == 1 and actual_failure == 0
missed_failure_count = predicted_alert == 0 and actual_failure == 1
maintenance_cost = parts_cost + labor_cost + lost_production_cost
cost_delta_rate = (baseline_cost - new_policy_cost) / baseline_cost
downtime_delta_rate = (baseline_downtime_minutes - new_policy_downtime_minutes) / baseline_downtime_minutes
detection_time_delta_rate = (baseline_detection_delay_minutes - new_policy_detection_delay_minutes) / baseline_detection_delay_minutes
```

If `baseline_total_cost` and `new_policy_total_cost` are available from the
company cost log, use them directly. If not, use the component cost fields only
as a traceability summary and do not claim actual cost reduction.

If `baseline_downtime_minutes` and `new_policy_downtime_minutes` are available
from the company downtime log, use them directly. If not, report total downtime
only and do not claim actual downtime reduction.

If `baseline_detection_delay_minutes` and `new_policy_detection_delay_minutes`
are available from the company alert/inspection log, use them directly. If not,
report alert lead time only and do not claim actual detection-time reduction.

## Claim Rules

- Public benchmark result: claim only as `official benchmark cost metric improvement`.
- Field validation: claim only after company-specific before/after data is collected.
- Do not claim actual 30% cost reduction or 85% detection-time reduction unless those values are calculated from field logs.
- The workflow remains approval-based; it does not execute unmanned maintenance commands.

## Minimum Acceptance For Field Proof

1. At least one complete before/after period for the same equipment group.
2. Consistent timestamp granularity and sensor units.
3. Confirmed ground-truth failure or repair labels.
4. Cost logs tied to work orders.
5. Baseline policy documented before applying the new model.
6. Direct before/after downtime and cost fields when claiming reduction rates.
"""


def create_field_validation_kit_zip() -> Path:
    """Bundle the protocol and CSV templates for a company data request."""
    files = [
        PROTOCOL_MD,
        DATA_TEMPLATE_CSV,
        MAINTENANCE_TEMPLATE_CSV,
        COST_TEMPLATE_CSV,
    ]
    with zipfile.ZipFile(FIELD_VALIDATION_KIT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.exists():
                archive.write(path, arcname=path.name)
    return FIELD_VALIDATION_KIT_ZIP


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    create_field_data_template().to_csv(DATA_TEMPLATE_CSV, index=False, encoding="utf-8-sig")
    create_field_maintenance_template().to_csv(MAINTENANCE_TEMPLATE_CSV, index=False, encoding="utf-8-sig")
    create_field_cost_template().to_csv(COST_TEMPLATE_CSV, index=False, encoding="utf-8-sig")
    PROTOCOL_MD.write_text(create_protocol_markdown(), encoding="utf-8")
    kit_zip = create_field_validation_kit_zip()
    print("Field validation protocol created successfully.")
    print(f"protocol_md: {PROTOCOL_MD}")
    print(f"data_template_csv: {DATA_TEMPLATE_CSV}")
    print(f"maintenance_template_csv: {MAINTENANCE_TEMPLATE_CSV}")
    print(f"cost_template_csv: {COST_TEMPLATE_CSV}")
    print(f"data_request_kit_zip: {kit_zip}")


if __name__ == "__main__":
    main()
