# Changelog

## 1.1.2 - 2026-05-31

- Updated Gemini/OpenAI model fallback handling and clearer quota/model-access errors.
- Verified final GenAI report evidence with `gemini-2.5-flash` for submitted materials.
- Kept API keys session-only and excluded them from reports, history, and release assets.
- Refreshed Full/Lite installer metadata and GitHub release URLs.

## 1.1.1 - 2026-05-13

- Added clearer Full/Lite result provenance fields to prediction CSV outputs.
- Added guarded partial field-validation reporting when cost logs are missing.
- Added Admin company field-validation screen for sensor labels and cost logs.
- Added release checksum generation for Full/Lite installers.
- Strengthened GUI workflow smoke checks and user-facing wording guardrails.

## 1.1.0 - 2026-05-13

- Added separate Full and Lite desktop distribution profiles.
- Added minimum GitHub upload-scope checks for source-first repository cleanup.
- Added field-validation report workflow for labeled company CSV and maintenance cost logs.
- Improved product UI wording for Lite/Full result boundaries.
- Added release readiness checks, distribution policy, and installer metadata.

## 1.0.0 - 2026-05-12

- Initial MaintiQ Predict desktop MVP installer.
- CSV prediction, risk monitoring, AI report, and approval-based work-order workflow.
- Streamlit Admin console for research and validation evidence.
