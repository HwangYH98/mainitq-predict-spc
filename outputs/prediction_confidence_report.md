# Prediction Confidence Report

## Scope

Confidence combines input data quality, AI4I reference-range checks, and validation-set probability calibration. It is not a field-certified reliability score.

- Selected calibration method: isotonic
- Quality score: 100.0
- Quality status: High
- Drift warning count: 0

## Brier Scores

| Method | Brier score |
|---|---:|
| raw | 0.028006 |
| sigmoid | 0.015253 |
| isotonic | 0.012369 |

## Guardrail

Low confidence means the user should inspect mapping, units, missing values, and training-distribution drift before using the risk result.