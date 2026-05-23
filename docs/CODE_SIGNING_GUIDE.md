# MaintiQ Predict 코드 서명 가이드

## 목적

Windows SmartScreen 경고를 줄이려면 설치파일에 Authenticode 코드 서명을 적용해야 합니다. 코드 서명은 앱 로직 문제가 아니라 배포 신뢰도 문제입니다.

서명만으로 SmartScreen 경고가 즉시 0이 된다고 보장되지는 않습니다. SmartScreen은 인증서, 다운로드 평판, 배포 이력, 사용자 신고 여부를 함께 봅니다. 그래도 공개 배포에는 서명된 설치파일을 사용하는 것이 기본입니다.

## 필요한 것

- Windows 코드 서명 인증서
- Windows SDK의 `signtool.exe`
- 빌드된 설치파일
  - `release\MaintiQ_Predict_Setup.exe`
  - `release\MaintiQ_Predict_Lite_Setup.exe`

## 인증서 저장소 thumbprint 방식

인증서가 Windows 인증서 저장소에 설치되어 있으면 thumbprint를 사용합니다.

```bat
set MAINTIQ_SIGN_CERT_SHA1=<certificate-thumbprint>
sign_windows_release.bat
```

## PFX 파일 방식

PFX 파일로 인증서를 보관하는 경우 아래 환경변수를 사용합니다.

```bat
set MAINTIQ_SIGN_PFX=C:\path\to\code-signing-cert.pfx
set MAINTIQ_SIGN_PFX_PASSWORD=<pfx-password>
sign_windows_release.bat
```

비밀번호가 없는 PFX라면 `MAINTIQ_SIGN_PFX_PASSWORD`는 설정하지 않아도 됩니다.

## 서명 후 확인

스크립트는 서명 후 아래 검증을 자동 실행합니다.

```bat
signtool verify /pa /v release\MaintiQ_Predict_Setup.exe
signtool verify /pa /v release\MaintiQ_Predict_Lite_Setup.exe
```

PowerShell 기반 상태 점검 도구도 제공합니다.

```bat
.\.venv\Scripts\python.exe tools\check_windows_signing_status.py
```

배포 직전에 서명을 필수로 강제하고 싶으면 아래처럼 실행합니다.

```bat
.\.venv\Scripts\python.exe tools\check_windows_signing_status.py --require-signed
```

## 주의사항

- 인증서 비밀번호를 코드, README, `.env`, GitHub commit에 저장하지 마세요.
- 설치파일은 Git에 commit하지 말고 GitHub Release artifact로 첨부하세요.
- 인증서가 없으면 `sign_windows_release.bat`는 실패하지 않고 skip합니다.
- 공개 배포 전에는 `release\checksums.txt`와 함께 설치파일을 배포하세요.
