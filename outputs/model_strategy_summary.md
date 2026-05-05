# Model Strategy Comparison

## Scope

This experiment compares baseline models, SMOTE variants, and threshold tuning on the same AI4I train/test split. It does not prove real factory cost reduction.

## Dataset

- Train rows: `8000`
- Test rows: `2000`
- Test failures: `68`
- Feature count: `8`

## Main Result

- Best PR-AUC: `XGBoost + tuned threshold` = `0.8014`
- Best F1-score: `XGBoost + tuned threshold` = `0.7752`

## Comparison Table

| Strategy | Threshold | Precision | Recall | F1 | ROC-AUC | PR-AUC | Alerts | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| XGBoost + tuned threshold | 0.87 | 0.8197 | 0.7353 | 0.7752 | 0.9736 | 0.8014 | 61 | 11 | 18 |
| XGBoost + SMOTE + tuned threshold | 0.80 | 0.6216 | 0.6765 | 0.6479 | 0.9632 | 0.7163 | 74 | 28 | 22 |
| XGBoost | 0.50 | 0.4444 | 0.8824 | 0.5911 | 0.9736 | 0.8014 | 135 | 75 | 8 |
| XGBoost + SMOTE | 0.50 | 0.4231 | 0.8088 | 0.5556 | 0.9632 | 0.7163 | 130 | 75 | 13 |
| Logistic Regression + SMOTE | 0.50 | 0.1484 | 0.8382 | 0.2522 | 0.9074 | 0.3878 | 384 | 327 | 11 |
| Logistic Regression | 0.50 | 0.1418 | 0.8235 | 0.2419 | 0.9069 | 0.3817 | 395 | 339 | 12 |

## Presentation-Safe Conclusion

PR-AUC 기준 최고 전략은 `XGBoost + tuned threshold` (0.8014)이고, F1-score 기준 최고 전략은 `XGBoost + tuned threshold` (0.7752)입니다. 이번 split에서는 XGBoost+SMOTE가 기본 XGBoost보다 recall을 높이지 못했습니다. 따라서 SMOTE는 항상 우수하다고 단정하지 않고, precision/recall/F1 trade-off 관점에서 선택합니다.

## Guardrail

Do not claim 85% detection-time reduction or 30% maintenance-cost reduction from this local experiment. Those require real factory before/after data.
