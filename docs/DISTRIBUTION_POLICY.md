# MaintiQ Predict Distribution Policy

## Official User Package

The official user-facing package is:

```text
release\MaintiQ_Predict_Setup.exe
```

This is the Full Windows desktop installer. It includes the runtime files needed by the PySide desktop app and is the only installer that should be presented as the user distribution.

Streamlit is a local operations/Admin validation surface. It is not the end-user installation package.

## GitHub Policy

Commit source code, tests, installer scripts, sample CSVs, and documentation.

Do not commit:

- `release/`
- `dist/`
- `build/`
- `outputs/`
- `data_external/`
- `.venv/`
- API keys, `.env`, passwords, or real company raw data

Attach `release\MaintiQ_Predict_Setup.exe` to a GitHub Release instead of committing it.

## Checksums

Generate release checksums after building the installer:

```powershell
.\.venv\Scripts\python.exe tools\create_release_checksums.py
```

The checksum file is:

```text
release\checksums.txt
```

Do not attach or document Lite installers as the official user package.

## Signing

Public distribution should use Authenticode signing when a certificate is available:

```powershell
set MAINTIQ_SIGN_CERT_SHA1=<certificate-thumbprint>
.\scripts\dev\local\sign_windows_release.bat
```

If no signing certificate is available, mark the GitHub Release notes as unsigned and local/academic distribution. Unsigned installers may show Windows SmartScreen warnings.
