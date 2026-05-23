# Industrial Engineering Evidence

## Scope

This note connects the implemented predictive-maintenance MVP to industrial-engineering concepts. It is intended for thesis background, evaluation framing, and claim guardrails.

Do not describe this artifact as real PLC/SCADA integration, live factory deployment, real company-data validation, 30% cost reduction, 85% detection-time reduction, or a commercial SaaS completion proof.

## OEE, MTBF, and MTTR Connection

| Metric | Formula | Meaning | How this system connects | Claim limit |
|---|---|---|---|---|
| OEE | `OEE = Availability x Performance x Quality` | Overall equipment effectiveness | High-risk alerts and work-order decisions can support Availability management in a future field pilot. | OEE is not calculated from AI4I alone. |
| MTBF | `MTBF = total operating time / number of failures` | Mean time between failures | Failure-risk history can become one input to MTBF monitoring when real operating-time logs exist. | MTBF improvement is not proven without field logs. |
| MTTR | `MTTR = total repair time / number of repairs` | Mean time to repair | Human-approved work-order traceability can later connect alerts to repair duration. | MTTR reduction is not proven without repair-time records. |

## Maintenance Strategy Positioning

| Strategy | Trigger | Strength | Limitation | Role in this project |
|---|---|---|---|---|
| Corrective maintenance | Repair after failure | Simple to operate | Unplanned downtime risk | Baseline strategy for discussion. |
| Preventive maintenance | Fixed schedule or usage interval | Easy planning | Can over-maintain healthy assets | Compared conceptually with threshold policies. |
| Predictive maintenance | Sensor and model-based risk signal | Prioritizes high-risk assets before failure | Requires data quality, model validation, and operator governance | Main direction of the MVP. |

## SPC Control-Chart Basis

The dashboard uses predictive SPC context to visualize failure probability and sensor signals with control-limit style interpretation.

```text
UCL = mean + 3 x sigma
LCL = mean - 3 x sigma
SPC alert = value > UCL or value < LCL
```

In this MVP, the control-limit context is derived from AI4I/local artifacts. A real site would need equipment-specific stable-period data before using the limits as approved process-control limits.

## FMEA/RPN Interpretation

Standard FMEA often uses:

```text
RPN = Severity x Occurrence x Detection
```

The implemented `risk_priority_score` is FMEA-inspired, not a replacement for a formal FMEA sheet.

| FMEA concept | System variable | Interpretation |
|---|---|---|
| Severity | `missed_failure_weight / false_alarm_weight` | Higher missed-failure cost increases priority. |
| Occurrence | `calibrated_probability` and `calibrated_probability >= policy_threshold` | Higher calibrated failure probability raises priority. |
| Detection | `quality_score` and quality warnings | Lower data quality increases review priority because detection reliability is weaker. |

## Risk Priority Score Formula

The current implementation calculates row-level priority as:

```text
risk_priority_score = clip(
    72 x calibrated_probability
  + 14 x I(calibrated_probability >= policy_threshold)
  + 0.14 x (100 - quality_score)
  + 10 x clip(missed_failure_weight / max(false_alarm_weight, 0.1), 0, 30) / 30,
  0,
  100
)
```

| Term | Role |
|---|---|
| `calibrated_probability` | Main failure-risk signal after probability calibration. |
| `policy_threshold` | Operating policy boundary such as precision-first, balanced, or recall-first. |
| `quality_score` | Penalizes missing values, conversion errors, out-of-range values, duplicates, and invalid category values. |
| `missed_failure_weight` | Relative cost of missing a real failure. Default implementation value is 15.0. |
| `false_alarm_weight` | Relative cost of inspecting a false alarm. Default implementation value is 1.0. |

- Latest generated quality score: `100.0`
- Latest generated quality status: `High`
- Latest selected calibration method: `isotonic`

## Operating Policy Thresholds

| Policy | Threshold | Precision | Recall | F1 | False alarms | Missed failures |
|---|---:|---:|---:|---:|---:|---:|
| `precision_first` | 0.34 | 0.8065 | 0.7353 | 0.7692 | 12 | 18 |
| `balanced` | 0.51 | 0.8305 | 0.7206 | 0.7717 | 10 | 19 |
| `recall_first` | 0.09 | 0.4203 | 0.8529 | 0.5631 | 80 | 10 |

## Cost Simulation Formula

The operating-value simulation uses relative cost units, not real currency.

```text
operating_cost_units =
    false_alarm_count x C_false_alarm
  + missed_failure_count x C_missed_failure
  + alert_count x C_planned_action

normalized_operating_cost =
    operating_cost_units / no_alert_baseline_cost
```

| Variable | Meaning |
|---|---|
| `false_alarm_count` | Alerts raised for rows without actual failure. |
| `missed_failure_count` | Actual failures not alerted by the policy. |
| `alert_count` | Total rows requiring operator attention. |
| `C_false_alarm` | Relative burden of unnecessary inspection. |
| `C_missed_failure` | Relative burden of missed failure or downtime. |
| `C_planned_action` | Relative burden of planned review/action. |

- Best balanced-scenario policy in the latest simulation: `xgboost_default`
- Best balanced-scenario normalized cost: `0.3088`

## Field Validation Readiness

| Validation level | Current status | What is still required |
|---|---|---|
| Local benchmark validation | Implemented with AI4I artifacts. | Keep split and artifact versions fixed. |
| Sample company-schema validation | Implemented with AI4I-derived sample data. | Do not label it as real company validation. |
| Real labeled company CSV validation | Supported when data is supplied. | Need approved company CSV with failure labels and timestamp/equipment context. |
| Shadow-mode field pilot | Structurally prepared through API/mock bridge/work-order flow. | Need site access, sensor gateway, security approval, and operator feedback. |
| Production PLC/SCADA deployment | Not implemented. | Need OT integration, network approval, monitoring, rollback, and maintenance-system integration. |

## Paper-Safe Claim

A safe thesis claim is that the system integrates failure-probability prediction, SPC-style monitoring, probability calibration, FMEA-inspired risk prioritization, normalized cost simulation, and human-approved work-order traceability into one reproducible product MVP.

## Claims To Avoid

- Real industrial-site validation is complete.
- Real PLC/SCADA operating-network connection is complete.
- The model proved 30% cost reduction or 85% detection-time reduction.
- The system is a finished commercial SaaS product.
- The risk priority score is a certified FMEA/RPN replacement.
