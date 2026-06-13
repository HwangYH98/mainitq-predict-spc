# MaintiQ Predict

MaintiQ Predict is a Windows desktop predictive-maintenance MVP. It loads sensor CSV rows, preprocesses them into the AI4I-compatible schema, estimates machine-failure risk, shows monitoring evidence, generates optional GenAI manager notes, and records human-approved work-order decisions.

The official user entrypoint is the Windows desktop app and installer. Streamlit is kept as an operator/Admin validation console. For browser-only evaluation, deploy the Streamlit entrypoints from GitHub with Streamlit Community Cloud.

## Final Evaluation Baseline

The current thesis/app decision baseline is fixed to the 60:20:20 validation design:

| Item | Value |
|---|---:|
| Train / validation / fixed test rows | 6,000 / 2,000 / 2,000 |
| Final decision probability | `raw_probability` |
| Final High Risk threshold | `0.86` |
| Fixed-test precision | `0.8065` |
| Fixed-test recall | `0.7353` |
| Fixed-test F1-score | `0.7692` |
| Fixed-test PR-AUC | `0.8118` |
| Fixed-test ROC-AUC | `0.9697` |
| Calibration selected by validation Brier | `isotonic` |
| Fixed-test isotonic Brier score | `0.012369` |

Legacy values are not the default app policy:

- `0.87` and F1 `0.7752` are the old 80:20 same-holdout exploratory threshold result.
- `0.51` and `0.34` are calibrated-probability reference policy values, not the default app decision threshold.

## Quick Start

### 1. Create the development environment

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

### 2. Run the desktop app

```powershell
.\01_Run_MaintiQ_Predict.bat
```

Direct execution:

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py
```

### 3. Run the Streamlit operator dashboard with one click

Streamlit cannot be opened by double-clicking a local `.py` or `.html` file. Use the root BAT file below. It starts a local Python server, opens the browser, and prints the session login details.

```powershell
.\04_Run_Streamlit_Dashboard.bat
```

The script creates a temporary operator password, copies it to the clipboard, starts Streamlit, and opens `http://127.0.0.1:8501`.

- URL: `http://127.0.0.1:8501`
- Login ID: `operator_01`
- Password: printed by the BAT file and copied to the clipboard

To use another port:

```powershell
$env:STREAMLIT_PORT="8503"
.\04_Run_Streamlit_Dashboard.bat
```

### 4. Run the research validation Admin console

```powershell
.\02_Run_Admin_Console.bat
```

The Admin console is separated from the operator dashboard. It shows research validation, accepted run artifacts, benchmark evidence, and reproducibility files without changing the Desktop or Streamlit operating policy.

- URL: `http://127.0.0.1:8502`
- Login ID: `admin`
- Password: entered into the BAT file for the current session only
- Accepted research run: fixed by `app/accepted_research_run.json`

Passwords and API keys are session-only. Do not store them in `.env`, README, outputs, screenshots, or Git history.

## Browser Deployment With Streamlit Cloud

Use this when reviewers need a URL that opens in a browser without installing Python or the desktop app.

Recommended Streamlit Cloud apps:

| Purpose | Entrypoint | Audience |
|---|---|---|
| Operator dashboard | `app/operator_dashboard.py` | Users who upload CSV files and review risk monitoring |
| Admin validation console | `app/admin_dashboard.py` | Reviewers checking accepted experiments, reproducibility, and audit evidence |

Deployment steps:

1. Push the repository to GitHub.
2. Open Streamlit Community Cloud and create a new app.
3. Select this repository, the `main` branch, and one entrypoint above.
4. In Advanced settings, select Python `3.12`.
5. Add secrets in the Streamlit Cloud settings, not in Git:

```toml
[auth]
operator_password = "set-a-reviewer-password"
admin_password = "set-an-admin-password"
```

The Cloud deployment uses `app/requirements.txt`, which excludes desktop-only packages such as `PySide6` and build/test tools. The root `requirements-lock.txt` remains the local reproducibility environment for code review and thesis validation.

Do not upload private factory data, `.env` files, API keys, or real company raw data to Streamlit Cloud. Uploaded CSV files and optional GenAI keys should be treated as session-only demo inputs.

## Reproduce Core Outputs

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe src\train_baseline.py
.\.venv\Scripts\python.exe src\thesis_methodology_validation.py
.\.venv\Scripts\python.exe src\stage4_explain.py
.\.venv\Scripts\python.exe src\predictive_spc.py
.\.venv\Scripts\python.exe src\future_deviation.py
.\.venv\Scripts\python.exe src\create_presentation_summary.py
```

Important output files:

- `outputs\threshold_summary.json`: final 0.86 raw-probability app policy.
- `outputs\legacy_threshold_summary_80_20.json`: old 0.87 exploratory result.
- `outputs\thesis_methodology_metrics.json`: 60:20:20 validation/test metrics.
- `outputs\spc_summary.json`: SPC-inspired risk-flow summary with training-normal reference limits.
- `outputs\spc_risk_chart.png`, `outputs\spc_control_chart.png`: updated SPC figures.

## Verification

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app desktop_app tools streamlit_app.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp outputs\pytest_basetemp_local
.\.venv\Scripts\python.exe src\verify_project.py
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
```

If Windows temp permissions cause pytest setup failures, keep `--basetemp outputs\pytest_basetemp_local`.

## Build Installer

```powershell
.\03_Build_User_Installer.bat
```

`release\MaintiQ_Predict_Setup.exe` should be attached to a GitHub Release. Do not commit the installer binary to the source repository.

## Data Scope and Claim Boundary

Allowed claims:

- AI4I 2020 public-data model training and fixed-test evaluation.
- Local desktop/Streamlit execution.
- Human-in-the-loop GenAI report and work-order workflow.
- SCANIA/public benchmark evidence only where the source data and metric scripts are present.

Do not claim without external evidence:

- Real PLC/SCADA production-network deployment.
- Real factory sensor streaming.
- Real company-data field validation.
- Proven KRW cost reduction or lead-time reduction.
- Automatic maintenance command execution.

## Repository Contents

```text
app/            Streamlit user/Admin screens
data/           AI4I base dataset
desktop_app/    Windows PySide6 desktop app
installer/      Inno Setup configuration
samples/        User prediction sample CSVs
scripts/dev/    Development and verification helpers
src/            Training, prediction, SPC, GenAI, validation engines
tests/          Automated tests
tools/          Distribution and runtime validation tools
```

Do not commit `.venv/`, `build/`, `dist/`, `release/`, `.env`, API keys, passwords, `data_external/`, or real company raw data.
