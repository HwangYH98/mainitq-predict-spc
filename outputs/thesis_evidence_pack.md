# Thesis Evidence Pack

## Defensible Claim

The system implements a reproducible product MVP that connects AI4I failure prediction, threshold tuning, SMOTE comparison, Predictive SPC, SHAP/GenAI explanation, and a human-approved work-order workflow in one local pipeline.

## Do Not Claim

- Real PLC/SCADA production network integration is complete.
- Real factory sensor streaming is deployed in production.
- Commercial cloud SaaS operation is complete.
- Automatic maintenance commands are executed without human approval.
- Real company data has proven performance improvement unless such data is supplied and evaluated.
- 85% detection-time reduction, 30% cost reduction, or validated factory ROI.

## Evidence Artifacts

| Artifact | Path | Paper use | Exists now |
|---|---|---|---:|
| Baseline model metrics | `outputs/metrics.json` | Logistic Regression vs XGBoost baseline comparison | True |
| SMOTE and threshold strategy comparison | `outputs/model_strategy_comparison.csv` | Class imbalance and operating-point trade-off table | True |
| Model strategy PR curve | `outputs/model_strategy_pr_curve.png` | Precision-recall visual comparison | True |
| SPC-only vs ML+SPC comparison | `outputs/spc_vs_ml_comparison.csv` | Rule-based SPC and ML alert strategy comparison | True |
| Operational value simulation | `outputs/operational_value_simulation.csv` | False-alarm/missed-failure normalized cost simulation | True |
| Product capability comparison | `outputs/product_capability_comparison.md` | Feature-level comparison with commercial reference systems | True |
| Workflow traceability summary | `outputs/workflow_traceability_summary.md` | Event-draft-decision traceability evidence | True |
| Company CSV preprocessing report | `outputs/company_preprocessing_report.md` | Column mapping, unit conversion, and data-quality diagnosis evidence | True |
| Probability calibration metrics | `outputs/probability_calibration_metrics.json` | Raw vs calibrated failure-probability reliability evidence | True |
| Risk priority queue | `outputs/company_risk_priority_queue.csv` | Risk-prioritized operator workflow evidence | True |
| Industrial engineering evidence | `outputs/industrial_engineering_evidence.md` | OEE/MTBF/MTTR, FMEA/RPN, SPC, cost simulation, and risk-priority formula | True |
| Open industrial validation metrics | `outputs/open_industrial_validation_metrics.csv` | Public industrial dataset adapter, alert strategy comparison, and lead-time/cost simulation | True |
| Open industrial lead-time report | `outputs/open_industrial_lead_time_report.md` | Early-warning lead-time definition and strategy comparison | True |
| Public industrial benchmark metrics | `outputs/public_industrial_validation_metrics.csv` | MetroPT-3, C-MAPSS, IMS, and FEMTO-style alert strategy comparison | True |
| Public industrial RUL metrics | `outputs/public_industrial_rul_metrics.csv` | RUL RMSE/MAE and NASA-style score comparison on public benchmark adapters | True |
| Public benchmark claims | `outputs/public_benchmark_claims.md` | Claim guardrails for public benchmark versus field proof | True |
| SCANIA official cost metrics | `outputs/scania_official_cost_metrics.csv` | Public benchmark class 0~4 official cost metric and rule-baseline improvement | True |
| SCANIA official cost report | `outputs/scania_official_cost_report.md` | Thesis-safe official cost metric claim and alert-burden guardrail | True |
| Field validation protocol | `outputs/field_validation_protocol.md` | Required field-data protocol for future real cost and lead-time proof | True |

## Commercial Reference Systems

| System | Product category | Best use in the paper |
|---|---|---|
| IBM Maximo | Commercial EAM/APM platform | Use as a functional reference, not as a direct performance baseline. |
| AWS IoT SiteWise | Industrial IoT data platform | Use as a functional reference, not as a direct performance baseline. |
| Azure IoT Operations | Industrial edge and cloud operations platform | Use as a functional reference, not as a direct performance baseline. |
| Siemens Insights Hub | Industrial IoT and asset-health platform | Use as a functional reference, not as a direct performance baseline. |

## Recommended Comparison Sentence

Rather than claiming superiority over commercial platforms, the thesis compares transparent model strategies and alert policies on the same AI4I test split, adds SCANIA official-cost evidence and public benchmark adapters for MetroPT-3, C-MAPSS, IMS, and FEMTO-style data, then shows how the selected risk signal is connected to explanation and human-approved work-order decisions.
