# Robust Validation Report

This run keeps the accepted 0.86 fixed-test app policy separate from repeated validation.

## Design

- Outer validation: 5 folds x 5 repeats = 25 evaluations
- Threshold and calibration selection: inner validation split only
- Outer fold labels: used only for final fold evaluation
- Hyperparameters: current baseline XGBoost settings reused

## Aggregate Out-of-Fold Metrics

- Precision: 0.7196
- Recall: 0.692
- F1-score: 0.7056
- PR-AUC: 0.7461
- ROC-AUC: 0.9731

## Bootstrap 95% Confidence Intervals

| Metric | Mean | Std | Median | Min | Max | 95% lower | 95% upper |
|---|---:|---:|---:|---:|---:|---:|---:|
| precision | 0.719523 | 0.010026 | 0.719734 | 0.683445 | 0.755089 | 0.699700 | 0.739077 |
| recall | 0.692378 | 0.011196 | 0.692625 | 0.650737 | 0.728614 | 0.670206 | 0.714454 |
| f1_score | 0.705634 | 0.008660 | 0.705794 | 0.674043 | 0.731590 | 0.688504 | 0.723010 |
| roc_auc | 0.973126 | 0.002088 | 0.973175 | 0.966120 | 0.979736 | 0.968932 | 0.976921 |
| pr_auc | 0.746137 | 0.010082 | 0.745980 | 0.711536 | 0.776904 | 0.727381 | 0.766113 |
| false_alarm_rate | 0.009475 | 0.000446 | 0.009461 | 0.007970 | 0.011096 | 0.008633 | 0.010351 |
| missed_failure_rate | 0.307622 | 0.011196 | 0.307375 | 0.271386 | 0.349263 | 0.285546 | 0.329794 |

## Claim Boundary

This result is still AI4I public-data internal repeated validation. It is not field deployment, real-time lead-time proof, or company-data performance proof.
