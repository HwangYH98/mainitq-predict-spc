# Operational Value Simulation

## Scope

This is a normalized cost simulation, not a real factory cost-reduction proof.
The units are relative weights for false alarms, missed failures, and planned actions.

## Balanced Scenario Result

| Policy | Precision | Recall | F1 | Alerts | False alarms | Missed failures | Normalized cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| XGBoost default threshold | 0.4444 | 0.8824 | 0.5911 | 135 | 75 | 8 | 0.3088 |
| ML + Predictive SPC combined | 0.6250 | 0.8088 | 0.7051 | 88 | 33 | 13 | 0.3314 |
| XGBoost tuned threshold | 0.8197 | 0.7353 | 0.7752 | 61 | 11 | 18 | 0.3735 |
| SPC-only torque rule | 0.8571 | 0.0882 | 0.1600 | 7 | 1 | 62 | 0.9245 |
| No alert baseline | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 68 | 1.0000 |

## Presentation-Safe Conclusion

In the balanced simulation, `XGBoost default threshold` has the lowest normalized operating cost (0.3088). This supports comparing alert-policy trade-offs, but it does not prove real downtime reduction or real maintenance-cost savings.

## Guardrail

Do not describe this as 85% faster detection, 30% cost reduction, or validated factory ROI.
