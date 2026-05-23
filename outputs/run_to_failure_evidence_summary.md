# Run-to-Failure Benchmark Evidence Summary

This file gathers public benchmark and field-validation evidence into one paper-ready index.
It supports public benchmark claims only; actual company cost reduction or lead-time reduction requires company logs.

## Public Industrial Benchmarks

- `public_industrial_validation_metrics.csv`: 24 rows.

| dataset_id | precision | recall | f1_score | pr_auc |
|---|---|---|---|---|
| metropt3 | 0.483057 | 0.522757 | 0.502123 | 0.303494 |
| metropt3 | 1.0 | 0.010143 | 0.020082 | 0.115865 |
| metropt3 | 0.447663 | 0.976593 | 0.613913 | 0.89413 |
| metropt3 | 0.874684 | 0.809623 | 0.840897 | 0.923992 |
| metropt3 | 0.886298 | 0.80078 | 0.841372 | 0.923992 |
| metropt3 | 0.886298 | 0.80078 | 0.841372 | 0.923992 |

## Lead-Time Metrics

- `public_industrial_lead_time_metrics.csv`: 24 rows.

| dataset_id | mean_lead_time_steps | early_warning_rate |
|---|---|---|
| metropt3 | 0.0 | 0.0 |
| metropt3 | 0.0 | 0.0 |
| metropt3 | 24.0 | 1.0 |
| metropt3 | 0.0 | 1.0 |
| metropt3 | 0.0 | 1.0 |
| metropt3 | 0.0 | 1.0 |

## RUL Metrics

- `public_industrial_rul_metrics.csv`: 8 rows.

| dataset_id |
|---|
| metropt3 |
| metropt3 |
| cmapss |
| cmapss |
| ims |
| ims |

## SCANIA Official Cost Metric

- `scania_official_cost_metrics.csv`: 6 rows.

| official_cost | normalized_cost | cost_improvement_vs_rule |
|---|---|---|
| 49548.0 | 0.863206 | 0.170175 |
| 55096.0 | 0.959861 | 0.077258 |
| 57002.0 | 0.993066 | 0.045337 |
| 57400.0 | 1.0 | 0.038671 |
| 57949.0 | 1.009564 | 0.029476 |
| 59709.0 | 1.040226 | 0.0 |

## Field Validation Readiness

- `field_validation_report.csv`: 1 rows.

| source_mode | precision | recall | false_alarm_count | missed_failure_count | maintenance_cost_delta_rate | claim_status |
|---|---|---|---|---|---|---|
| template_demo | 1.0 | 1.0 | 0 | 0 | 0.129032 | template_demo_not_field_proof |

## Metadata

- `public_industrial_validation_metadata.json`: generated. List records: 4.

## Claim Guardrail

- Public benchmark improvements can be stated only for the named public dataset and metric.
- Actual plant cost savings require before/after maintenance cost logs.
- Actual detection-time reduction requires failure timestamps and first-alert timestamps.
- Lite runtime results are not a replacement for Full research-model benchmark results.
