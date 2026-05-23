# GitHub Upload Scope

This repository uses a minimal source-first upload scope. It should contain source code, product documentation, sample data, tests, reproducibility scripts, and only a very small set of evidence/template files that are useful without rerunning the project. It should not contain local runtime state, bulk generated outputs, screenshots, benchmark prediction dumps, external raw datasets, API keys, virtual environments, or generated installer binaries.

Most `outputs/` files are regenerable local artifacts. They should stay local unless explicitly listed below. This keeps the GitHub repository focused on code and reproducibility instead of generated result dumps. If a file can be rebuilt by `run_verify.bat` or a validation script, do not commit it unless it is explicitly listed in the allowed evidence/template set.

## Commit To GitHub

- `AGENTS.md`
- `README.md`
- `GITHUB_UPLOAD_SCOPE.md`
- `.gitignore`
- `requirements.txt`
- `src/`
- `app/`
- `desktop_app/`
- `tools/`
- `installer/`
- `docs/`
- `samples/`
- `data/ai4i2020.csv`
- `streamlit_app.py`
- `run_*.bat`
- `run_*.ps1`
- `build_desktop_app.bat`
- `build_desktop_installer.bat`
- `build_desktop_lite_app.bat`
- `build_desktop_lite_installer.bat`
- `run_tests.bat`
- `sign_windows_release.bat`
- `tests/`
- `CHANGELOG.md`
- selected minimal `outputs/` files:
  - `outputs/thesis_evidence_pack.md`
  - `outputs/industrial_engineering_evidence.md`
  - `outputs/field_validation_protocol.md`
  - `outputs/field_data_template.csv`
  - `outputs/field_cost_template.csv`
  - `outputs/run_to_failure_evidence_summary.md`

## Do Not Commit

- `.venv/`
- `.codex/`
- `__pycache__/`
- `build/`
- `dist/`
- `release/`
- `*.spec`
- `.env`
- `.env.*`
- `*.key`
- files or folders containing secrets
- `outputs/operations.db`
- `outputs/operations_lite.db`
- `outputs/realtime_stream/`
- `outputs/work_order_drafts/`
- `outputs/custom_company_model/*.joblib`
- generated prediction row dumps such as `outputs/*predictions*.csv`
- generated benchmark result tables and plots not listed above
- generated dashboard/app screenshots such as `outputs/*screenshot*`
- temporary smoke-test and installer-validation outputs
- `data_external/`
- `local_presentation_notes/`
- real company raw CSVs or maintenance logs

## Release Artifact

`release/MaintiQ_Predict_Setup.exe` and `release/MaintiQ_Predict_Lite_Setup.exe` are installer artifacts. Attach them to a GitHub Release. Do not commit them into the Git repository.

Suggested final commit message before Release upload:

```text
Finalize MaintiQ Predict desktop MVP packaging and validation tooling
```

## Before Push Checklist

Run:

```powershell
.\.venv\Scripts\python.exe tools\check_github_upload_scope.py
.\.venv\Scripts\python.exe tools\list_github_upload_candidates.py
.\.venv\Scripts\python.exe -m pytest -q
git status --short --ignored=matching
```

Expected result:

- upload-scope check passes
- API key pattern matches: `0`
- `outputs/` commit candidates are limited to the selected minimal evidence/template files above
- ignored folders include `.venv/`, `build/`, `dist/`, `release/`, `data_external/`, `local_presentation_notes/`
- no `operations.db` or raw company data is staged
