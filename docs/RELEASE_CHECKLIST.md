# MaintiQ Predict Release Checklist

Run this checklist before uploading the installer to GitHub Releases.

## Build

```powershell
.\.venv\Scripts\python.exe tools\check_release_readiness.py
.\03_Build_User_Installer.bat
```

Expected output:

```text
release\MaintiQ_Predict_Setup.exe
release\checksums.txt
```

## Smoke Test

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --workflow-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --click-workflow-test
.\.venv\Scripts\python.exe -m pytest -q --basetemp outputs\pytest_basetemp_release
```

`--basetemp` avoids Windows user temp-folder permission issues during pytest setup.

## Security

Confirm:

- API key pattern matches are zero.
- `release/*.exe` is not staged for commit.
- `.venv/`, `outputs/`, `release/`, `data_external/`, `.env`, key files, and real company raw data are not tracked or staged.
- `operations.db`, external raw data, and local notes are not staged.
- `outputs/` files remain local/regenerable unless explicitly selected as small evidence files.

## Signing

If a signing certificate is available:

```powershell
set MAINTIQ_SIGN_CERT_SHA1=<certificate-thumbprint>
.\scripts\dev\local\sign_windows_release.bat
```

If no certificate is available, mark the GitHub Release notes as unsigned and local/academic distribution.

## GitHub Release

Attach:

- `release\MaintiQ_Predict_Setup.exe`
- `release\checksums.txt`

Do not commit installer binaries to the repository.
