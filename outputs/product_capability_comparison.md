# Product Capability Comparison

## Scope

This is a functional positioning table, not a claim that this system outperforms commercial SaaS products.
Commercial systems are stronger in production integration, security, scale, and enterprise maintenance operations.
This system focuses on reproducible AI4I experiments and an integrated ML+SPC+GenAI+approval workflow.

## Comparison Table

| System | Sensor input | Model reproducibility | SPC integration | Explainability | Work-order workflow | Deployment level | Research reproducibility |
|---|---|---|---|---|---|---|---|
| IBM Maximo | Enterprise asset and IoT data integration | Product-managed; internal implementation is not a reproducible AI4I experiment | Asset monitoring and analytics capabilities; SPC workflow depends on configuration | Product analytics and AI features vary by deployment | Strong enterprise maintenance workflow | Commercial production platform | Low for public dataset benchmarking |
| AWS IoT SiteWise | Industrial data collection, modeling, monitoring, and anomaly detection | Cloud-service workflow; benchmark pipeline is user-defined | Operational metrics and anomaly detection; SPC workflow is not the central research artifact | Depends on user-built analytics layer | Requires integration with maintenance systems | Commercial cloud platform | Medium when users publish their own pipeline |
| Azure IoT Operations | Industrial device/asset connectivity and cloud integration | Cloud/edge service workflow; benchmark model details are user-defined | Supports industrial analytics scenarios; SPC workflow depends on solution design | Depends on connected AI services and custom implementation | Requires integration with business/maintenance applications | Commercial cloud/edge platform | Medium when users publish their own pipeline |
| Siemens Insights Hub | Machine/process data ingestion and asset health solutions | Product/solution-managed; public benchmark reproduction is user-defined | Asset health, maintenance, and quality prediction solutions | Depends on configured solution and AI model | Enterprise workflow depends on integration | Commercial industrial IoT platform | Low to medium for public benchmark comparison |
| This system | CSV upload, local API, file-drop playback, MQTT/OPC UA mock bridge | Full local AI4I split, metrics, SMOTE comparison, threshold tuning, saved artifacts | ML probability, SPC control-chart context, and combined alert comparison | SHAP factor view plus Gemini/OpenAI GenAI manager report | Human-approved draft, approve/reject/needs_review decision log | Local/product MVP; not a production SaaS deployment | High within the provided code/data/artifacts |

## Paper-Safe Positioning

Do not claim overall superiority over IBM Maximo, AWS IoT SiteWise, Azure IoT Operations, or Siemens Insights Hub.
Use them as commercial reference systems, then compare this project on reproducibility, transparent model evaluation, SPC+ML alert evidence, GenAI explanation, and approval workflow traceability.
