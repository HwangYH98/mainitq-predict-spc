# MaintiQ Predict 배포 정책

## 지원 패키지

- 정밀 분석 모드 설치파일: `MaintiQ_Predict_Setup.exe`
  - XGBoost/SHAP 기반 정밀 분석, 연구 검증, Admin 확인에 사용합니다.
- 빠른 점검 모드 설치파일: `MaintiQ_Predict_Lite_Setup.exe`
  - 작은 설치본, 경량 운영 점수, 일상 점검과 배포 확인에 사용합니다.

설치파일은 GitHub Release 첨부 파일로 배포합니다. 소스 저장소에는 commit하지 않습니다.

두 모드는 계산 엔진이 다르므로 결과가 다를 수 있습니다. 보고서, 논문, 운영 기록에서는 하나의 모드를 일관되게 사용하세요.

## 버전 관리

애플리케이션 버전은 `desktop_app/version.py`에 정의합니다. Full/Lite Inno Setup script의 `MyAppVersion` 값과 반드시 일치해야 합니다.

## Checksum

두 설치파일을 모두 만든 뒤 아래 checksum 파일을 생성합니다.

```text
release\checksums.txt
```

이 파일은 정밀 분석 모드와 빠른 점검 모드 설치파일의 SHA256 hash를 포함합니다. 소스 관리 대상이 아니라 Release 첨부용 artifact입니다.

## 코드 서명

공개 배포에는 유효한 코드 서명 인증서를 이용한 Authenticode 서명을 사용하는 것이 좋습니다. Unsigned 설치파일은 게시자 평판이 없기 때문에 Windows SmartScreen 경고가 뜰 수 있습니다.

서명 workflow:

```powershell
set MAINTIQ_SIGN_CERT_SHA1=<certificate-thumbprint>
.\sign_windows_release.bat
```

PFX 파일로 서명하는 경우:

```powershell
set MAINTIQ_SIGN_PFX=C:\path\to\code-signing-cert.pfx
set MAINTIQ_SIGN_PFX_PASSWORD=<pfx-password>
.\sign_windows_release.bat
```

서명 인증서가 설정되어 있지 않으면 서명 단계는 정상 skip됩니다. 이 경우 설치파일은 로컬/연구용 배포 artifact로 취급합니다.
자세한 절차와 SmartScreen 주의사항은 `docs\CODE_SIGNING_GUIDE.md`에 정리되어 있습니다.

## 업데이트 정책

이 프로젝트에는 무인 백그라운드 업데이트가 포함되어 있지 않습니다. 앱의 `업데이트 확인` 기능은 GitHub Release의 최신 버전을 조회하고, 새 버전이 있으면 Release 페이지를 열도록 안내합니다. 설치파일 교체와 재설치는 사용자가 직접 수행합니다.

## 제거와 로컬 데이터

설치 제거 시 알려진 runtime 생성 파일은 제거 규칙에 따라 정리합니다.

- 로컬 운영 DB
- 생성된 field-validation report
- 생성된 screenshot
- realtime stream folder
- work-order draft folder

API key와 비밀번호는 앱이 저장하지 않습니다.

## Crash log

예상하지 못한 데스크톱 앱 오류는 아래 위치에 저장됩니다.

```text
%LOCALAPPDATA%\MaintiQ Predict\logs\
```

호환성용 복사본은 아래 위치에 저장될 수 있습니다.

```text
%TEMP%\MaintiQ_Predict_error.log
```

이 log는 로컬 전용이며 자동 업로드되지 않습니다.

## SmartScreen

SmartScreen 평판은 서명된 설치파일과 배포 이력에 영향을 받습니다. 공개 배포에는 서명된 Release artifact를 사용하고, 버전별 changelog를 유지하세요.
