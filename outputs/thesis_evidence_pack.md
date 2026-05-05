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

## Commercial Reference Systems

| System | Product category | Best use in the paper |
|---|---|---|
| IBM Maximo | Commercial EAM/APM platform | Use as a functional reference, not as a direct performance baseline. |
| AWS IoT SiteWise | Industrial IoT data platform | Use as a functional reference, not as a direct performance baseline. |
| Azure IoT Operations | Industrial edge and cloud operations platform | Use as a functional reference, not as a direct performance baseline. |
| Siemens Insights Hub | Industrial IoT and asset-health platform | Use as a functional reference, not as a direct performance baseline. |

## Recommended Comparison Sentence

Rather than claiming superiority over commercial platforms, the thesis compares transparent model strategies and alert policies on the same AI4I test split, then shows how the selected risk signal is connected to explanation and human-approved work-order decisions.
