# Field Validation Guide

This guide defines what is needed to turn MaintiQ Predict from a product MVP into
a site-specific field validation study.

## Required files

MaintiQ Predict needs three company-side CSV files for a defensible field
validation.

| File | Purpose | Required for |
|---|---|---|
| `field_data_template.csv` | Sensor rows with timestamps and actual failure labels | Model performance recheck |
| `field_maintenance_template.csv` | Work orders, maintenance actions, start/end times | Lead-time and traceability analysis |
| `field_cost_template.csv` | Downtime, parts cost, labor cost, lost production cost, baseline/new policy cost, baseline/new policy downtime, baseline/new policy detection delay | Cost, downtime, and detection-time impact analysis |

The generated bundle is:

```text
outputs\field_validation_data_request_kit.zip
```

Send this ZIP to the company or lab partner when requesting data.

## Claim rules

- Sensor labels only: precision, recall, false alarm, and missed failure can be
  rechecked.
- Sensor labels plus maintenance history: lead time and work-order traceability
  can be partially analyzed.
- Sensor labels plus maintenance history plus cost logs: cost delta can be
  calculated only when `baseline_total_cost` and `new_policy_total_cost` are
  present.
- Downtime reduction can be calculated only when `baseline_downtime_minutes` and
  `new_policy_downtime_minutes` are present.
- Detection-time reduction can be calculated only when
  `baseline_detection_delay_minutes` and `new_policy_detection_delay_minutes`
  are present.
- Actual cost reduction and detection-time improvement must not be claimed unless
  the company-provided logs include the fields needed for those calculations.

## Command

Regenerate the protocol and templates:

```bat
.\.venv\Scripts\python.exe src\create_field_validation_protocol.py
```

Generate a report from company files:

```bat
.\.venv\Scripts\python.exe src\evaluate_field_validation_report.py ^
  --field-data path\to\labeled_sensor.csv ^
  --maintenance-data path\to\maintenance_history.csv ^
  --cost-data path\to\downtime_cost.csv
```

If `--cost-data` is omitted, the report will explicitly mark cost and downtime
claims as unsupported.

## Data privacy

Do not commit company raw data to Git. Keep raw files outside the repository or
under an ignored folder such as `data_external/`.
