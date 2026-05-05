# SPC-only vs ML+SPC Alert Comparison

## Scope

This comparison uses AI4I UDI-order playback rows. It is not a live factory stream and does not prove real maintenance cost reduction.

## Result Table

| Strategy | Precision | Recall | F1 | Alerts | FP | FN | TP |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPC-only torque control limit | 0.8571 | 0.0882 | 0.1600 | 7 | 1 | 62 | 6 |
| ML selected threshold | 0.8197 | 0.7353 | 0.7752 | 61 | 11 | 18 | 50 |
| ML + Predictive SPC combined | 0.6250 | 0.8088 | 0.7051 | 88 | 33 | 13 | 55 |

## Presentation-Safe Conclusion

F1-score 기준 최고 alert 전략은 `ML selected threshold` (0.7752)입니다. 단일 torque SPC rule은 7개 alert만 발생시켜 recall이 0.0882였고, ML+SPC combined는 88개 alert와 recall 0.8088를 보였습니다. 이 결과는 실제 비용 절감 실증이 아니라, rule-based SPC-only와 ML probability 기반 alert의 탐지 특성 차이를 보여주는 로컬 비교입니다.

## Guardrail

Use this as an alert-strategy comparison, not as a claim that a real factory reduced downtime or maintenance cost.
