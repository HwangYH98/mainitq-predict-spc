# APPROVED CODEX EXPERIMENT PLAN

## Metadata

- Created at (KST): 2026-06-12T18:15:22+09:00
- Created at (UTC): 2026-06-12T09:15:22+00:00
- Timezone: Asia/Seoul
- Turn ID: `2026-06-12-codex-experiment-plan-approved`
- Target repository: `HwangYH98/mainitq-predict-spc`
- Inspected branch: `main`
- Latest visible planning baseline: `8c367fc` (`Align thesis app policy with 0.86 validation threshold`)
- Approval state: approved for detailed planning
- Implementation state: not started
- Next approval required: implementation approval for a bounded phase
- User score: not supplied
- Provisional implementation confidence: 50/100 until the repository is cloned, baseline artifacts are reproduced, and the full test suite passes

## 1. Purpose

This plan translates eight thesis criticisms into repository-level Codex work. It separates:

1. evidence that can be strengthened by code and public datasets;
2. evidence that requires real company data or human experts;
3. manuscript organization that should change only after new evidence is accepted.

The plan must not manufacture real factory evidence, expert ratings, external generalization, cost savings, or improved metrics. Negative results are valid. The accepted thesis/app baseline remains unchanged until an explicit result-acceptance step.

## 2. Current Repository Findings to Reuse

The repository already contains substantial relevant code.

- `src/thesis_methodology_validation.py`
  - performs stratified 60:20:20 splitting;
  - fits the model on training data;
  - selects the raw threshold on validation F1;
  - selects calibration using validation Brier score;
  - evaluates the fixed test set;
  - performs five seed-level repetitions;
  - in the current implementation, each seed is split again, the model is refit, and the threshold is reselected on that seed's validation set.
- `src/create_field_validation_protocol.py`
  - creates field sensor, maintenance, and cost templates.
- `src/evaluate_field_validation_report.py`
  - provides a starting point for field evidence reporting.
- `src/verify_company_generalization.py`
  - validates a custom-company schema path, but AI4I-derived demo data must never be described as real field validation.
- `src/realtime_ops.py` and `src/watch_realtime_folder.py`
  - provide operational/shadow-mode integration points.
- `src/download_public_industrial_datasets.py`
  - supports MetroPT-3, C-MAPSS, and IMS.
- `src/predictive_spc.py`
  - creates the current AI4I UDI-order SPC-inspired analysis.
- `src/scania_official_cost_validation.py`
  - uses the official SCANIA class-cost matrix and already reports cost, macro-F1, balanced accuracy, class recall, and alert-like rate.
- `src/stage4_explain.py`, `desktop_app/genai.py`, and `tests/test_genai_provider.py`
  - provide the GenAI generation boundary and provider tests.
- `README.md`
  - records the accepted 0.86 app policy and core reproduction commands.
- `tests/test_thesis_methodology_validation.py`
  - is the correct regression-test entry point for threshold-selection behavior.

Codex should extend these files and extract small shared utilities rather than replacing the application.

## 3. Non-Negotiable Rules

1. Do not overwrite accepted top-level output files during development.
2. Write every new experiment to `outputs/experiments/<run_id>/`.
3. Record commit, dirty-tree state, platform, Python, package versions, command, data hashes, seeds, timestamps, and artifact hashes.
4. Never commit real company raw data, identifiers, API keys, passwords, or private work-order records.
5. Fail closed when required labels, timestamps, or baseline-policy records are missing.
6. Test data must not influence fitting, feature selection, threshold selection, calibration, or policy selection.
7. Do not revise acceptance criteria after seeing results.
8. Do not change thesis numbers automatically.
9. Preserve the accepted 0.86 default app policy until a separately reviewed policy migration.
10. Real savings claims require directly observed company before/after records.

## 4. Recommended Implementation Order

1. Phase 0: freeze the current baseline.
2. Phase 1: add shared run/provenance and metric utilities.
3. Workstream 5: stronger repeated validation and bootstrap intervals.
4. Workstream 8: one-command reproducibility.
5. Workstream 2: real timestamp-based public SPC validation.
6. Workstream 3: multi-case GenAI evaluation.
7. Workstream 4: constrained SCANIA policy analysis.
8. Workstream 1: field-validation readiness, then real shadow validation only if data are supplied.
9. Workstream 7: verified prior-art matrix.
10. Workstream 6: manuscript relocation of the legacy 80:20 result after evidence acceptance.

This order puts the most reliable and reusable foundations first.

# Phase 0 — Baseline Freeze

## Goal

Prove that the checked-out repository reproduces the accepted thesis/app baseline before new code is added.

## Codex actions

1. Clone the repository.
2. Record:
   - `git rev-parse HEAD`;
   - `git status --porcelain`;
   - branch name;
   - Python version;
   - lock-file hash;
   - AI4I hash.
3. Create branch `experiment/thesis-evidence-strengthening`.
4. Run:
   - `src/train_baseline.py`;
   - `src/thesis_methodology_validation.py`;
   - compileall;
   - pytest;
   - `src/verify_project.py`;
   - desktop `--check`;
   - desktop `--engine-smoke-test`.
5. Copy baseline outputs into an immutable run folder.

## Files to add

- `src/experiment_run.py`
- `tests/test_experiment_run.py`

## Required outputs

- `baseline_manifest.json`
- `baseline_metrics_snapshot.json`
- `baseline_test_report.json`
- `artifact_manifest.csv`
- `command_log.txt`

## Exit criteria

- fixed-test precision 0.8065;
- recall 0.7353;
- F1 0.7692;
- PR-AUC 0.8118;
- ROC-AUC 0.9697;
- isotonic Brier 0.012369;
- current tests pass;
- no accepted artifact is silently overwritten.

If these conditions fail, stop. Do not start new experiments.

# Phase 1 — Shared Experiment Infrastructure

## Goal

Create the smallest common layer needed by all experiments.

## Files

- `src/experiment_run.py`
  - run directory;
  - provenance;
  - status;
  - exception recording;
  - artifact manifest.
- `src/data_integrity.py`
  - SHA-256;
  - schema validation;
  - duplicate/time-order checks;
  - identifier leakage checks.
- `src/evaluation_metrics.py`
  - classification metrics;
  - event metrics;
  - alert-rate metrics;
  - bootstrap summaries.
- tests for each module.

## Design constraints

Use functions, dataclasses, pathlib, JSON, CSV, and Parquet. Do not introduce a framework, database, plugin architecture, or experiment-tracking server.

## Exit criteria

- deterministic unit tests;
- existing tests pass;
- existing app and output paths remain compatible.

# Workstream 1 — Actual Field Data Validation

## What can be solved

Codex can build an auditable field-validation and shadow-mode pipeline. It cannot create actual field evidence without real de-identified company data.

## Two explicit modes

### Readiness mode

Uses templates or clearly synthetic fixtures. Allowed claim:

> A field-validation protocol and execution pipeline were implemented.

### Field-evidence mode

Requires actual de-identified company sensor, failure, maintenance, baseline-policy, downtime, and cost records. Only this mode may support bounded site-specific evidence.

## Data contract

Extend the current templates into five related tables.

### `field_sensor_events.csv`

- `site_id_hash`
- `equipment_id_hash`
- `timestamp`
- `source_system`
- `schema_version`
- sensor values
- operating-condition variables
- quality flags

### `field_failure_events.csv`

- equipment hash
- failure ID
- failure timestamp
- failure type
- confirmation source
- label confidence

### `field_maintenance_events.csv`

- work-order hash
- equipment hash
- linked alert
- decision time
- maintenance start/end
- action
- result

### `field_baseline_policy.csv`

- prior rule or reactive policy
- effective period
- thresholds
- staffing/alert-capacity assumptions

### `field_cost_events.csv`

- downtime
- labor
- parts
- lost production
- currency
- observed/imputed flag

## Files to modify/add

- extract shared logic into `src/field_validation.py`;
- update `src/create_field_validation_protocol.py`;
- update `src/evaluate_field_validation_report.py`;
- update `src/verify_company_generalization.py`;
- integrate optional shadow logging with `src/realtime_ops.py`;
- add `src/run_field_shadow_validation.py`;
- add:
  - `tests/test_field_validation_schema.py`;
  - `tests/test_field_shadow_validation.py`;
  - `tests/test_field_claim_guardrails.py`.

## Evaluation design

1. Freeze a historical training interval.
2. Freeze a later policy-selection/calibration interval.
3. Reserve the newest interval as untouched shadow test.
4. Prevent the same failure episode from crossing intervals.
5. Compare:
   - existing baseline policy;
   - fixed 0.86 policy;
   - a site candidate chosen before shadow test.
6. Report:
   - event recall;
   - equipment-day false alarms;
   - median/IQR lead time;
   - missed events;
   - alerts per shift;
   - approval/review/rejection;
   - observed downtime/cost deltas only when complete direct records exist.

## Outputs

- `field_data_quality_report.json`
- `field_schema_validation.csv`
- `field_shadow_predictions.parquet`
- `field_event_metrics.csv`
- `field_policy_comparison.csv`
- `field_lead_time_distribution.csv`
- `field_workload_by_shift.csv`
- `field_cost_report.csv`
- `field_claim_status.json`
- `field_validation_summary.md`

`field_claim_status.json` values:

- `supported`
- `not_supported`
- `not_evaluable`
- `readiness_only`

## Acceptance

- missing data and leakage are detected;
- synthetic fixtures are visibly marked;
- no savings claim without observed before/after data;
- all reported metrics are traceable to source rows/events;
- data owner reviews the interpretation.

## Codex prompt

> Inspect the existing field-validation, company-adapter, real-time, and workflow modules. Implement a minimal chronological shadow-mode field-validation pipeline with strict schemas, claim guardrails, provenance, and tests. Never label AI4I-derived or synthetic data as real field evidence. Keep company data outside Git and stop when labels, timestamps, or baseline-policy records are insufficient.

# Workstream 2 — Real Timestamp-Based SPC

## Goal

Add a separate public time-series experiment. Keep the AI4I UDI chart as exploratory only.

MetroPT-3 is the preferred first dataset because the repository already supports its download and it provides timestamped compressor signals and failure reports.

## Data design

- path: `data_external/metropt3/`;
- parse and normalize timestamps;
- reject duplicate/backwards timestamps;
- default chronological split:
  - first month: baseline/development;
  - later months: evaluation;
- encode published failure-event windows;
- preregister alert horizons such as 30 min, 2 h, 6 h, 24 h;
- collapse adjacent alarms into alert episodes.

## Minimal methods

1. Shewhart limits on standardized residuals.
2. EWMA on standardized residuals.
3. Risk-score limits fitted only on the normal reference period.

Add CUSUM only if these are stable and the thesis needs it.

## Files

- `src/metropt3_loader.py`
- `src/time_series_spc_validation.py`
- additions to `src/evaluation_metrics.py`
- update `src/create_run_to_failure_evidence_summary.py`
- tests:
  - `test_metropt3_loader.py`
  - `test_time_series_spc_validation.py`
  - `test_event_metrics.py`

## Metrics

- event detection rate;
- median/IQR lead time;
- false alarms per operating day;
- alert episodes per day;
- episode precision;
- event detection by horizon;
- post-event detection delay;
- percent time in alarm.

## Outputs

- dataset manifest;
- failure windows;
- reference-period definition;
- point metrics;
- event metrics;
- alert episodes;
- lead-time distribution;
- timeline and event-panel figures;
- thesis-safe report.

## Acceptance

- limits use only pre-evaluation normal data;
- event definitions are source-traceable;
- time-order tests pass;
- lead time and false alarms/day are reported;
- negative results are retained;
- no real-time deployment claim.

## Codex prompt

> Add a MetroPT-3 timestamp-based SPC benchmark. Use a chronological normal reference period and later failure-event evaluation. Compare Shewhart, EWMA, and risk-score limits. Implement event lead-time and false-alarm metrics, tests, machine-readable outputs, and a thesis-safe report. Never use future data to fit limits.

# Workstream 3 — Multi-Case GenAI Evaluation

## Goal

Move from one illustration to a small, pre-registered functional/factuality study. Expert validation remains optional and must use real reviewers.

## Case set

Create `data/genai_eval_cases.jsonl` with at least:

- 5 low-risk cases;
- 5 boundary cases;
- 5 high-risk cases;
- 3 incomplete/adversarial cases.

Each record contains structured input, probability, threshold, SHAP factors, SPC state, allowed facts, forbidden facts, and required approval language.

## Protocol

- freeze provider/model/prompt/temperature;
- store prompt hash;
- deterministic run at temperature 0;
- optional 5 repetitions at temperature 0.2;
- preserve every response;
- support offline replay without an API key.

## Automated checks

- probability and numeric facts match;
- named sensors exist;
- no unsupported cause is asserted;
- no autonomous maintenance command;
- human approval is explicit;
- no invented maintenance history/cost;
- boundary cases contain uncertainty.

## Human review

Blank form with:

- factual consistency 1–5;
- usefulness 1–5;
- clarity 1–5;
- uncertainty 1–5;
- unsafe recommendation yes/no;
- missing approval boundary yes/no.

If two or more qualified reviewers participate, compute agreement. Otherwise do not claim expert validation.

## Files

- `src/genai_evaluation.py`
- `src/genai_response_checks.py`
- `data/genai_eval_cases.jsonl`
- `docs/genai_human_review_form.csv`
- fixtures under `tests/fixtures/genai/`
- tests for checks and offline replay.

## Outputs

- manifest;
- raw responses;
- automatic checks;
- repeat-consistency table;
- blank human form;
- human summary only when data exist;
- report.

## Preregistered automatic targets

- numeric mismatch 0%;
- unsupported sensor names 0%;
- autonomous commands 0%;
- approval boundary 100%;
- invented history 0%.

Failure must remain visible.

## Codex prompt

> Build a versioned GenAI evaluation harness covering low, boundary, high, and incomplete inputs. Freeze prompt/model metadata, preserve raw responses, support offline replay, and test factual consistency and prohibited autonomous instructions. Generate but do not fabricate a human-review dataset.

# Workstream 4 — SCANIA Constrained Policy Analysis

## Goal

Preserve the all-alert result as a failure mode and add leakage-safe workload-constrained policies.

## Design

- train on official training data;
- use training-only folds for model/calibration/policy selection;
- evaluate official validation once;
- compare:
  - no alert;
  - rule;
  - SPC-style;
  - logistic;
  - XGBoost argmax;
  - unconstrained expected cost;
  - constrained expected cost.

Preregister candidate alert-like-rate caps: 5%, 10%, 20%, 30%, subject to documented operational rationale.

## Selection method

Apply an auditable penalty/bias to alert classes and choose it on training-only folds. Freeze it before official validation. Do not tune on official validation labels.

## Metrics

- official cost;
- normalized cost;
- macro-F1;
- balanced accuracy;
- class recall;
- alert-like rate;
- predicted class distribution;
- Pareto dominance.

## Files

- `src/scania_policy_selection.py`
- refactor `src/scania_official_cost_validation.py`
- tests:
  - cost matrix;
  - policy constraints;
  - no final-validation selection leakage.

## Outputs

- selection folds;
- candidates;
- final metrics;
- Pareto table;
- cost-vs-alert and cost-vs-F1 plots;
- report.

## Acceptance

- all-alert remains visible;
- constraints selected without final labels;
- no success claim based on cost alone;
- negative constrained results retained.

## Codex prompt

> Extend SCANIA with training-only constrained policy selection. Keep the all-alert result as a baseline. Evaluate official validation once and jointly report cost, macro-F1, balanced accuracy, class recall, class distribution, and alert-like rate. Add leakage-prevention tests and Pareto outputs.

# Workstream 5 — Stronger Repeated Validation

## Goal

Add a stronger uncertainty estimate while preserving the fixed-test result.

## First task

Write a regression test proving the current seed routine:

- resplits for each seed;
- refits the model;
- selects a threshold on that seed's validation set;
- evaluates that seed's test set.

## Main design

- repeated stratified 5-fold outer CV;
- 5 repeats = 25 outer test folds;
- inside each outer-training partition:
  - inner stratified validation or 4-fold inner CV;
  - fit preprocessing/model only inside training;
  - select threshold and calibration inside inner data;
  - evaluate untouched outer test.

Use fixed model hyperparameters initially. Do not combine this with a broad tuning search.

## Bootstrap

From out-of-fold predictions:

- 2,000 stratified resamples;
- fixed seed;
- percentile 95% intervals for precision, recall, F1, PR-AUC, ROC-AUC, false-alarm rate, and missed-failure rate.

Also report fold/repeat mean, SD, median, min, max.

## Files

- refactor reusable functions from `thesis_methodology_validation.py`;
- `src/robust_validation.py`;
- `src/bootstrap_intervals.py`;
- tests:
  - seed threshold reselection;
  - no leakage;
  - bootstrap;
  - deterministic rerun.

## Outputs

- fold metrics;
- selected thresholds;
- out-of-fold predictions;
- summary JSON;
- bootstrap CSV;
- metric and threshold plots;
- report.

## Acceptance

- 25 outer evaluations;
- no outer-test label used for selection;
- same seed reproduces same outputs;
- uncertainty and threshold variation reported;
- fixed F1 0.7692 remains separately labeled;
- no cherry-picked replacement.

## Codex prompt

> Test the current seed-level threshold reselection. Then implement repeated stratified 5-fold outer validation with inner threshold/calibration selection, leakage-safe out-of-fold predictions, and 2,000 stratified bootstrap intervals. Keep fixed hyperparameters and preserve the current 0.86 representative baseline.

# Workstream 6 — Move Legacy 80:20 Results

## Goal

After new evidence is accepted, remove 0.87 from the main result flow but preserve transparency.

## Repository outputs first

Generate:

- `legacy_80_20_table.csv`
- `legacy_80_20_figure.png`
- `legacy_80_20_appendix.md`
- `main_results_replacement.md`
- `manuscript_patch_manifest.json`

Do not edit the HWPX until these are reviewed.

## Final manuscript change

- move Table 5.2 and Figure 5.4 to appendix;
- retain one body cross-reference;
- refresh numbering, TOC, lists, and PDF;
- archive the previous manuscript.

## Acceptance

- 0.87 only in appendix/historical references;
- 0.86 is the only primary policy;
- legacy values match their source JSON.

## Codex prompt

> Prepare a reviewed manuscript patch package that moves the legacy 80:20/0.87 table and figure to an appendix. Keep the main results limited to the validation-separated 0.86 design. Do not edit the HWPX until the patch package is accepted.

# Workstream 7 — Prior-Art Matrix

## Goal

Create a source-verifiable comparison rather than a generic narrative.

## Evidence CSV

`docs/literature_evidence.csv` columns:

- citation ID;
- full reference;
- DOI/URL;
- source type;
- dataset;
- task;
- model;
- evaluation design;
- reported metrics;
- result;
- explainability;
- GenAI/RAG;
- human approval/workflow;
- audit trail;
- limitations;
- thesis difference;
- page/section locator;
- verification status.

Use `NR` for not reported. Never infer a performance number.

## Initial studies

- Carvalho et al.;
- Zonta et al.;
- Cummins et al.;
- PARAM/RAG maintenance;
- one directly relevant SPC or cost-sensitive study.

## Files

- `tools/build_literature_matrix.py`
- `tools/validate_literature_evidence.py`
- `docs/literature_evidence.csv`
- `docs/literature_comparison.csv`
- `docs/literature_comparison.md`
- `docs/literature_claim_audit.md`
- tests for schema and locators.

## Acceptance

- every row has a direct locator;
- every comparison statement maps to verified evidence;
- no fabricated metric;
- review papers identified as reviews;
- integration contribution visible without algorithmic novelty claim.

## Codex prompt

> Build a source-verifiable literature matrix workflow. Validate citation identity, locators, and required fields; generate Markdown only from approved rows; use NR for unreported fields. Do not summarize papers that have not been supplied and checked.

# Workstream 8 — One-Command Reproducibility

## Goal

Turn existing commands into auditable quick and full pipelines.

## Files

- `scripts/reproduce_quick.ps1`
- `scripts/reproduce_all.ps1`
- `src/verify_reproduction_bundle.py`
- tests for manifest and drift checks.

## Quick mode

- environment checks;
- AI4I hash;
- accepted baseline;
- tests;
- app smoke check;
- no external large data;
- no API.

## Full mode

- quick mode;
- robust validation;
- MetroPT-3 if present;
- SCANIA if present;
- GenAI offline replay;
- optional live API only with explicit flag;
- field readiness;
- manuscript summaries.

## Every run writes

- `run_manifest.json`
- `command_log.txt`
- `environment.json`
- `data_manifest.json`
- `artifact_manifest.csv`
- `verification_report.json`

Do not regenerate `requirements-lock.txt` during reproduction. Lock generation is a separate maintenance operation.

## CI

- quick mode only;
- no external large downloads;
- no API;
- no company data;
- optional manual public-benchmark workflow.

## Acceptance

- one command works on clean Windows checkout;
- optional data show `SKIPPED`, not success;
- required metric drift causes nonzero exit;
- no secrets in logs;
- new run directory each time.

## Codex prompt

> Implement quick and full PowerShell reproduction entrypoints using existing commands. Capture commit, dirty status, platform, package and data hashes, commands, outputs, and verification. Never regenerate the lock file during reproduction. Skip optional inputs honestly and fail on accepted baseline drift.

# Shared Output Layout

```text
outputs/
  experiments/
    <timestamp>-<short_commit>-<experiment_id>/
      run_manifest.json
      command_log.txt
      environment.json
      data_manifest.json
      metrics/
      predictions/
      figures/
      reports/
      artifact_manifest.csv
  manuscript/
    candidate/
    accepted/
```

# Testing Loop

For each workstream:

1. baseline test;
2. smallest implementation;
3. unit tests;
4. miniature synthetic end-to-end test;
5. targeted tests;
6. full existing suite;
7. schema review;
8. plot review;
9. claim-language review;
10. bounded repair and rerun.

Required existing commands:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app desktop_app tools streamlit_app.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp outputs\pytest_basetemp_local
.\.venv\Scripts\python.exe src\verify_project.py
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
```

# Manuscript Claim Matrix

| Evidence | Minimum condition | Allowed statement |
|---|---|---|
| field readiness | schemas and pipeline only | field-validation protocol implemented |
| field shadow evidence | real chronological data and labels | site/period-bounded shadow result |
| observed operations | complete comparable cost/downtime records | bounded observed delta |
| MetroPT-3 | timestamped event metrics | public time-series early-warning result |
| GenAI automatic | multi-case factual/safety checks | multi-case functional evaluation |
| GenAI expert | qualified reviewers plus agreement | bounded expert evaluation |
| SCANIA constrained | final-only and nondegenerate | public benchmark trade-off |
| robust validation | leakage-safe 25 outer folds and CI | repeated-CV estimate and interval |
| literature matrix | verified locators | direct prior-art comparison |
| reproduction | clean checkout quick pass | one-command core reproducibility |

# Pull Request Sequence

1. experiment infrastructure and baseline freeze;
2. robust validation;
3. reproduction scripts;
4. MetroPT-3 SPC;
5. GenAI evaluation;
6. SCANIA constraints;
7. field pipeline;
8. literature tooling;
9. manuscript patch.

Do not combine all workstreams into one PR.

# Definition of Done

The program is complete only when:

- all implemented experiments have deterministic tests;
- real-field claims are data-gated;
- time-series SPC reports lead time and false alarms/day;
- GenAI is multi-case tested without fabricated experts;
- SCANIA jointly reports cost, quality, and workload;
- repeated validation is leakage-safe with intervals;
- legacy 80:20 results are appendix-only;
- literature comparison is source-verifiable;
- clean checkout reproduces core outputs with one command;
- repository artifacts and manuscript claims agree;
- unresolved limitations remain explicit.

# Progress

- [x] User approved plan creation.
- [x] Current repository structure inspected.
- [x] Detailed plan written.
- [ ] Repository cloned into an implementation workspace.
- [ ] Exact HEAD and baseline artifacts frozen.
- [ ] Implementation approved.
- [ ] Any code changed.
- [ ] Any new experiment run.
- [ ] Any thesis metric changed.

# Recommended First Implementation Approval

Approve only:

- Phase 0;
- Phase 1;
- Workstream 5;
- Workstream 8.

This first slice strengthens the statistical and reproducibility foundation without requiring private data or external APIs. Field, SPC, GenAI, and SCANIA work should start only after that foundation passes review.
