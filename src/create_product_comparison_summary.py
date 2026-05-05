from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

COMPARISON_CSV = OUTPUT_DIR / "product_capability_comparison.csv"
COMPARISON_MD = OUTPUT_DIR / "product_capability_comparison.md"
EVIDENCE_PACK_MD = OUTPUT_DIR / "thesis_evidence_pack.md"


PRODUCT_ROWS = [
    {
        "system": "IBM Maximo",
        "category": "Commercial EAM/APM platform",
        "sensor_input": "Enterprise asset and IoT data integration",
        "model_reproducibility": "Product-managed; internal implementation is not a reproducible AI4I experiment",
        "spc_integration": "Asset monitoring and analytics capabilities; SPC workflow depends on configuration",
        "explainability": "Product analytics and AI features vary by deployment",
        "work_order_workflow": "Strong enterprise maintenance workflow",
        "deployment_level": "Commercial production platform",
        "research_reproducibility": "Low for public dataset benchmarking",
        "reference_url": "https://www.ibm.com/products/maximo",
    },
    {
        "system": "AWS IoT SiteWise",
        "category": "Industrial IoT data platform",
        "sensor_input": "Industrial data collection, modeling, monitoring, and anomaly detection",
        "model_reproducibility": "Cloud-service workflow; benchmark pipeline is user-defined",
        "spc_integration": "Operational metrics and anomaly detection; SPC workflow is not the central research artifact",
        "explainability": "Depends on user-built analytics layer",
        "work_order_workflow": "Requires integration with maintenance systems",
        "deployment_level": "Commercial cloud platform",
        "research_reproducibility": "Medium when users publish their own pipeline",
        "reference_url": "https://aws.amazon.com/iot-sitewise/",
    },
    {
        "system": "Azure IoT Operations",
        "category": "Industrial edge and cloud operations platform",
        "sensor_input": "Industrial device/asset connectivity and cloud integration",
        "model_reproducibility": "Cloud/edge service workflow; benchmark model details are user-defined",
        "spc_integration": "Supports industrial analytics scenarios; SPC workflow depends on solution design",
        "explainability": "Depends on connected AI services and custom implementation",
        "work_order_workflow": "Requires integration with business/maintenance applications",
        "deployment_level": "Commercial cloud/edge platform",
        "research_reproducibility": "Medium when users publish their own pipeline",
        "reference_url": "https://learn.microsoft.com/en-us/azure/iot-operations/overview-iot-operations",
    },
    {
        "system": "Siemens Insights Hub",
        "category": "Industrial IoT and asset-health platform",
        "sensor_input": "Machine/process data ingestion and asset health solutions",
        "model_reproducibility": "Product/solution-managed; public benchmark reproduction is user-defined",
        "spc_integration": "Asset health, maintenance, and quality prediction solutions",
        "explainability": "Depends on configured solution and AI model",
        "work_order_workflow": "Enterprise workflow depends on integration",
        "deployment_level": "Commercial industrial IoT platform",
        "research_reproducibility": "Low to medium for public benchmark comparison",
        "reference_url": "https://www.siemens.com/en-us/products/insights-hub/solutions/",
    },
    {
        "system": "This system",
        "category": "Product MVP and reproducible research pipeline",
        "sensor_input": "CSV upload, local API, file-drop playback, MQTT/OPC UA mock bridge",
        "model_reproducibility": "Full local AI4I split, metrics, SMOTE comparison, threshold tuning, saved artifacts",
        "spc_integration": "ML probability, SPC control-chart context, and combined alert comparison",
        "explainability": "SHAP factor view plus Gemini/OpenAI GenAI manager report",
        "work_order_workflow": "Human-approved draft, approve/reject/needs_review decision log",
        "deployment_level": "Local/product MVP; not a production SaaS deployment",
        "research_reproducibility": "High within the provided code/data/artifacts",
        "reference_url": "Local repository artifacts",
    },
]


EVIDENCE_FILES = [
    {
        "artifact": "Baseline model metrics",
        "path": "outputs/metrics.json",
        "paper_use": "Logistic Regression vs XGBoost baseline comparison",
    },
    {
        "artifact": "SMOTE and threshold strategy comparison",
        "path": "outputs/model_strategy_comparison.csv",
        "paper_use": "Class imbalance and operating-point trade-off table",
    },
    {
        "artifact": "Model strategy PR curve",
        "path": "outputs/model_strategy_pr_curve.png",
        "paper_use": "Precision-recall visual comparison",
    },
    {
        "artifact": "SPC-only vs ML+SPC comparison",
        "path": "outputs/spc_vs_ml_comparison.csv",
        "paper_use": "Rule-based SPC and ML alert strategy comparison",
    },
    {
        "artifact": "Operational value simulation",
        "path": "outputs/operational_value_simulation.csv",
        "paper_use": "False-alarm/missed-failure normalized cost simulation",
    },
    {
        "artifact": "Product capability comparison",
        "path": "outputs/product_capability_comparison.md",
        "paper_use": "Feature-level comparison with commercial reference systems",
    },
    {
        "artifact": "Workflow traceability summary",
        "path": "outputs/workflow_traceability_summary.md",
        "paper_use": "Event-draft-decision traceability evidence",
    },
]


def write_product_markdown(comparison: pd.DataFrame) -> None:
    """Write a thesis-safe product capability comparison."""
    rows = [
        "# Product Capability Comparison",
        "",
        "## Scope",
        "",
        "This is a functional positioning table, not a claim that this system outperforms commercial SaaS products.",
        "Commercial systems are stronger in production integration, security, scale, and enterprise maintenance operations.",
        "This system focuses on reproducible AI4I experiments and an integrated ML+SPC+GenAI+approval workflow.",
        "",
        "## Comparison Table",
        "",
        "| System | Sensor input | Model reproducibility | SPC integration | Explainability | Work-order workflow | Deployment level | Research reproducibility |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, row in comparison.iterrows():
        rows.append(
            f"| {row['system']} | {row['sensor_input']} | {row['model_reproducibility']} | "
            f"{row['spc_integration']} | {row['explainability']} | {row['work_order_workflow']} | "
            f"{row['deployment_level']} | {row['research_reproducibility']} |"
        )
    rows.extend(
        [
            "",
            "## Paper-Safe Positioning",
            "",
            "Do not claim overall superiority over IBM Maximo, AWS IoT SiteWise, Azure IoT Operations, or Siemens Insights Hub.",
            "Use them as commercial reference systems, then compare this project on reproducibility, transparent model evaluation, SPC+ML alert evidence, GenAI explanation, and approval workflow traceability.",
            "",
        ]
    )
    COMPARISON_MD.write_text("\n".join(rows), encoding="utf-8")


def write_evidence_pack(comparison: pd.DataFrame) -> None:
    """Write a compact thesis evidence pack with claim guardrails."""
    rows = [
        "# Thesis Evidence Pack",
        "",
        "## Defensible Claim",
        "",
        (
            "The system implements a reproducible product MVP that connects AI4I failure prediction, "
            "threshold tuning, SMOTE comparison, Predictive SPC, SHAP/GenAI explanation, and a human-approved "
            "work-order workflow in one local pipeline."
        ),
        "",
        "## Do Not Claim",
        "",
        "- Real PLC/SCADA production network integration is complete.",
        "- Real factory sensor streaming is deployed in production.",
        "- Commercial cloud SaaS operation is complete.",
        "- Automatic maintenance commands are executed without human approval.",
        "- Real company data has proven performance improvement unless such data is supplied and evaluated.",
        "- 85% detection-time reduction, 30% cost reduction, or validated factory ROI.",
        "",
        "## Evidence Artifacts",
        "",
        "| Artifact | Path | Paper use | Exists now |",
        "|---|---|---|---:|",
    ]
    for item in EVIDENCE_FILES:
        exists = (PROJECT_ROOT / item["path"]).exists()
        rows.append(
            f"| {item['artifact']} | `{item['path']}` | {item['paper_use']} | {exists} |"
        )

    rows.extend(
        [
            "",
            "## Commercial Reference Systems",
            "",
            "| System | Product category | Best use in the paper |",
            "|---|---|---|",
        ]
    )
    for _, row in comparison.iterrows():
        if row["system"] == "This system":
            continue
        rows.append(
            f"| {row['system']} | {row['category']} | Use as a functional reference, not as a direct performance baseline. |"
        )

    rows.extend(
        [
            "",
            "## Recommended Comparison Sentence",
            "",
            (
                "Rather than claiming superiority over commercial platforms, the thesis compares transparent "
                "model strategies and alert policies on the same AI4I test split, then shows how the selected "
                "risk signal is connected to explanation and human-approved work-order decisions."
            ),
            "",
        ]
    )
    EVIDENCE_PACK_MD.write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    """Create commercial reference and thesis evidence-pack artifacts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    comparison = pd.DataFrame(PRODUCT_ROWS)
    comparison.to_csv(COMPARISON_CSV, index=False, encoding="utf-8-sig")
    write_product_markdown(comparison)
    write_evidence_pack(comparison)

    print("Product capability comparison finished successfully.")
    print(f"comparison_csv: {COMPARISON_CSV}")
    print(f"comparison_md: {COMPARISON_MD}")
    print(f"evidence_pack: {EVIDENCE_PACK_MD}")


if __name__ == "__main__":
    main()
