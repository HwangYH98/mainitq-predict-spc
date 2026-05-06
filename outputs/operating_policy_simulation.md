# Operating Policy Simulation

## Scope

These thresholds are derived from the AI4I validation/test split and are not factory-approved operating policies.

- Selected policy for the latest company CSV prediction: `balanced`

| Policy | Threshold | Precision | Recall | F1 | Alerts | False alarms | Missed failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| Precision-first | 0.34 | 0.8065 | 0.7353 | 0.7692 | 62 | 12 | 18 |
| Balanced | 0.51 | 0.8305 | 0.7206 | 0.7717 | 59 | 10 | 19 |
| Recall-first | 0.09 | 0.4203 | 0.8529 | 0.5631 | 138 | 80 | 10 |

## Guardrail

Use these policies to discuss trade-offs. Do not claim real factory threshold approval or actual cost reduction.