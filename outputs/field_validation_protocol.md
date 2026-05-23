# Field Validation Protocol

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
