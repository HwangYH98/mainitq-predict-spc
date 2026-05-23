# MaintiQ Predict Release Checklist

Run this checklist before uploading installer artifacts to GitHub Releases.

## Build

```powershell
.\.venv\Scripts\python.exe tools\check_release_readiness.py
.\build_desktop_app.bat
.\build_desktop_installer.bat
.\build_desktop_lite_app.bat
.\build_desktop_lite_installer.bat
```

## Smoke Test

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --workflow-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --click-workflow-test
.\.venv\Scripts\python.exe desktop_app\lite_main.py --workflow-smoke-test
.\.venv\Scripts\python.exe desktop_app\lite_main.py --click-workflow-test
.\.venv\Scripts\python.exe -m pytest -q
```

## Security

```powershell
.\.venv\Scripts\python.exe tools\check_github_upload_scope.py
.\.venv\Scripts\python.exe tools\list_github_upload_candidates.py
```

Confirm:

- API key pattern matches are zero.
- `release/*.exe` is not staged for commit.
- `operations.db`, external raw data, and local notes are not staged.
- Most `outputs/` files are treated as regenerable local artifacts and are not committed.
- Commit scope is limited to source code, tests, scripts, samples, templates, and selected small evidence files.

## Signing

If a signing certificate is available:

```powershell
set MAINTIQ_SIGN_CERT_SHA1=<certificate-thumbprint>
.\sign_windows_release.bat
```

If the certificate is supplied as a PFX file:

```powershell
set MAINTIQ_SIGN_PFX=C:\path\to\code-signing-cert.pfx
set MAINTIQ_SIGN_PFX_PASSWORD=<pfx-password>
.\sign_windows_release.bat
```

If no certificate is available, mark the Release notes as unsigned and local/academic distribution.
See `docs\CODE_SIGNING_GUIDE.md` for the signing and SmartScreen notes.

## GitHub Release

Attach these files to the GitHub Release:

- `release\MaintiQ_Predict_Setup.exe`
- `release\MaintiQ_Predict_Lite_Setup.exe`
- `release\checksums.txt`

Do not commit installer binaries to the repository.

Suggested commit message for the source-code update:

```text
Finalize MaintiQ Predict desktop MVP packaging and validation tooling
```
