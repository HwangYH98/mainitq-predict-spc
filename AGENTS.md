# MaintiQ Predict Codex Instructions

## Project Goal
MaintiQ Predict is a Windows desktop predictive-maintenance MVP. It lets an operator load sensor CSV data, run preprocessing and failure-risk prediction, review monitoring charts, generate an optional GenAI manager report, and record human-approved work-order decisions.

The Streamlit Admin console is kept separately for research validation, model experiments, public benchmark evidence, audit checks, and reproducibility.

## Current Scope
- Product app: native PySide6 desktop app in `desktop_app/`.
- Admin console: Streamlit app in `app/admin_dashboard.py`.
- Core engines: training, preprocessing, prediction, SPC, GenAI reporting, local API, SQLite operation history, and benchmark scripts in `src/`.
- Data baseline: `data/ai4i2020.csv`.
- Reproducible outputs: selected files under `outputs/`.
- Installer build: `build_desktop_app.bat` and `build_desktop_installer.bat`.

## Implemented Boundary
- Stage 1~20 local integration flow exists as a local MVP.
- Gemini/OpenAI GenAI reporting is supported through session-only API keys.
- Local event, work-order draft, and operator decision history use SQLite and CSV exports.
- SCANIA and other public benchmark adapters support reproducible research evidence when source data is available.
- Field-validation templates exist for future company data collection.

## Do Not Claim Without External Evidence
- Real PLC/SCADA production-network integration is complete.
- Real factory sensor streaming is deployed.
- Real company-data performance validation is complete.
- Real cost reduction or lead-time reduction has been proven.
- Automatic maintenance commands are executed.
- This is a complete commercial SaaS platform.

## Product UI Rules
- The user-facing desktop app must look like an operational product.
- Do not expose research/development terms in the user app: `capstone`, `presentation`, `PoC`, `Demo`, `Stage`, or their Korean equivalents.
- Keep research, thesis, benchmark, and validation wording in the Admin console or generated evidence documents only.
- API keys and passwords must never be written to files, README, outputs, screenshots, or Git history.

## Coding Style
- Keep modules focused and readable.
- Prefer explicit data contracts over hidden assumptions.
- Raise clear errors for missing files, malformed CSV, model failures, and API failures.
- Preserve existing verified behavior unless the user explicitly asks to change it.
- Do not revert unrelated local edits.

## Verification Commands
Run these from the repository root:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app desktop_app tools streamlit_app.py
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --screenshot outputs\maintiq_predict_screenshot.png
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe src\verify_project.py
cmd /c "run_verify.bat < NUL"
```

For installer work:

```bat
.\build_desktop_app.bat
.\build_desktop_installer.bat
```

## GitHub Scope
Commit code, documentation, sample CSVs, scripts, and reproducible core outputs.

Do not commit:
- `.venv/`
- `build/`, `dist/`, `release/`, `*.spec`
- `.env`, key files, secret files
- `outputs/operations.db`
- `outputs/realtime_stream/`
- `outputs/work_order_drafts/`
- `data_external/`
- `local_presentation_notes/`
- real company raw data

`release/MaintiQ_Predict_Setup.exe` should be attached to a GitHub Release, not committed into the code repository.
